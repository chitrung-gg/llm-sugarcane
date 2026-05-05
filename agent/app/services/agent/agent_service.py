import asyncio
import os
import time
from typing import Any, Dict, List, Optional, AsyncContextManager, cast
import uuid
from warnings import deprecated

import aioboto3
from fastapi import HTTPException
from langfuse import Langfuse, propagate_attributes
from langfuse.types import TraceContext
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langgraph.types import Command
from langgraph.errors import GraphInterrupt
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langfuse.langchain import CallbackHandler
from loguru import logger
from opentelemetry import trace
import json

from pydantic import BaseModel
from sympy import Q

from app.utils.files.files_classifier import is_genomic_file
from app.utils.observability.tracing import tracing
from app.services.workspace.workspace_service import WorkspaceService
from app.common.constants import (
    LANGFUSE_GRAPH_OBSERVATION_NAME, 
    LANGGRAPH_STATE_MAX_ITERATIONS, 
    ObservationType, 
    SYSTEM_OWNER_ID, 
    StreamEventType,
    UserFeedbackAction,
    EventKind
)
from app.services.llm.llm_service import LLMService
from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem, ThreadTitleOutput
from app.schemas.agent.streaming import StreamChunk
from app.configs.storage.databases import langgraph_connection_pool
from app.core.graph.nodes.agent_graph_node import AgentGraphNode

class AgentService:
    def __init__(
        self,
        graph: CompiledStateGraph,
        workspace_service: WorkspaceService,
        llm_service: LLMService,
        langfuse_client: Langfuse
    ):
        self.graph = graph
        self.workspace_service = workspace_service
        self.llm_service = llm_service
        self.langfuse_client = langfuse_client

    @tracing(observation_type=ObservationType.AGENT)
    @deprecated("Use 'process_langgraph_chat_stream()' instead")
    async def process_langgraph_chat(
        self,
        thread_id: uuid.UUID,
        query: str,
        project_id: Optional[uuid.UUID] = None,
        dataset_ids: Optional[List[uuid.UUID]] = None
    ) -> AgentResponse:
        """Executes reasoning strictly using pre-ingested datasets."""
        start_time = time.time()
        callbacks = []
        execution_id = uuid.uuid4()

        # 1. Grab OTel Span Context
        current_otel_span = trace.get_current_span()
        span_context = current_otel_span.get_span_context()
        otel_trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
        
        # 2. Create the trace context mapping
        trace_ctx: TraceContext | None = {"trace_id": otel_trace_id} if otel_trace_id else None
            
        # 3. Start Langfuse Observation
        with self.langfuse_client.start_as_current_observation(
            name=LANGFUSE_GRAPH_OBSERVATION_NAME,
            as_type="agent",
            trace_context=trace_ctx
        ) as root_span:
            config: RunnableConfig = {
                "configurable": {
                    "thread_id": str(thread_id)
                },
                "callbacks": callbacks 
            }
            try:
                with propagate_attributes(
                    session_id=str(thread_id),
                    tags=["agent_chat"]
                ):
                    langfuse_callback = CallbackHandler(
                        trace_context={
                            "trace_id": root_span.trace_id,
                            "parent_span_id": root_span.id 
                        }
                    )
                    callbacks.append(langfuse_callback)
                    
                    #  Hydrate Workspace Context
                    active_project_name = None
                    if project_id:
                        project = await self.workspace_service.get_project(project_id)
                        if project:
                            active_project_name = project.name
                    
                    # Fallback to state if already exists
                    existing_state = await self.graph.aget_state(config)
                    if not active_project_name and existing_state and existing_state.values:
                        active_project_name = existing_state.values.get("active_project_name")
                    
                    active_project_name = active_project_name or "Default Project"

                    active_datasets = []
                    if dataset_ids:
                        datasets = await self.workspace_service.get_datasets_by_ids(dataset_ids)
                        for ds in datasets:
                            ds_files = []
                            for f in ds.files:
                                ds_files.append({
                                    "file_name": f.file_name,
                                    "file_type": str(f.file_type),
                                    "rustfs_uri": f.rustfs_uri
                                })
                            
                            active_datasets.append({
                                "dataset_id": str(ds.id),
                                "dataset_name": ds.name,
                                "files": ds_files
                            })
                    
                    if not active_datasets and existing_state and existing_state.values:
                        active_datasets = existing_state.values.get("active_datasets", [])
                    
                    # Check for duplicate user message to avoid history pollution on retry
                    messages_to_add = []
                    should_add_query = True
                    if existing_state and existing_state.values and existing_state.values.get("messages"):
                        last_msg = existing_state.values["messages"][-1]
                        if isinstance(last_msg, HumanMessage) and last_msg.content == query:
                            logger.info(f"Detected retry for same query in thread {thread_id}. Skipping duplicate HumanMessage.")
                            should_add_query = False
                    
                    if should_add_query:
                        messages_to_add.append(HumanMessage(content=query))
                    
                    # Persist thread and user message
                    await self._ensure_thread_exists(thread_id, project_id)
                    await self._save_chat_message(thread_id=thread_id, role="user", content=query, execution_id=execution_id)

                    # Trigger title generation if it doesn't exist yet
                    async with langgraph_connection_pool.connection() as conn:
                        cursor = await conn.execute("SELECT title FROM chat_threads WHERE thread_id = %s", (thread_id,))
                        row = await cursor.fetchone()
                        if row and not row['title']:
                            asyncio.create_task(self._generate_and_update_title(thread_id, query))

                    # Build initial state - CLEAR TURN-BASED STATE
                    initial_state = {
                        "query": query,
                        "messages": messages_to_add,      
                        "active_project_name": active_project_name,
                        "active_datasets": active_datasets,
                        "iteration_count": 0,
                        "execution_id": execution_id,
                        "start_time": time.time(),
                        "plan": [],          # Overwrite historical plan
                        "past_steps": [],      # Reset historical observations
                        "final_answer": ""     # Reset final answer
                    }

                    # Langgraph executes entirely within the Langfuse root_span
                    final_state = await self.graph.ainvoke(initial_state, config=config)

                    # Consolidate Sources & Build Response
                    raw_sources = final_state.get("sources_used", [])
                    consolidated_sources = await self._consolidate_sources(raw_sources)
                    process_time = time.time() - start_time

                    thoughts = []
                    for msg in final_state.get("messages", []):
                        if msg.type == AIMessage.type and msg.additional_kwargs.get("is_thought") and msg.additional_kwargs.get("execution_id") == str(execution_id):
                            thoughts.append(msg.content)
                            # Persist thought
                            await self._save_chat_message(
                                thread_id=thread_id,
                                role="assistant",
                                content=msg.content,
                                type="thought",
                                execution_id=execution_id
                            )

                    final_answer = final_state.get("final_answer", "No answer generated.")
                    # Persist final answer
                    await self._save_chat_message(
                        thread_id=thread_id,
                        role="assistant",
                        content=final_answer,
                        type="answer",
                        execution_id=execution_id
                    )

                    agent_response = AgentResponse(
                        thread_id=thread_id,
                        answer=final_answer,
                        thoughts=thoughts,
                        rag_sources=consolidated_sources, 
                        web_results=final_state.get("web_results", []),
                        tool_executions=final_state.get("tool_results", []),
                        execution_time=process_time,
                        execution_id=execution_id
                    )

                    # Instead of set_trace_io, update the span's own attributes
                    root_span.update(
                        input={
                            "user_query": query,
                            "project": active_project_name,
                            "dataset": active_datasets
                        },
                        output={"final_answer": agent_response.answer}
                    )

                    return agent_response
            except Exception as e:
                logger.error(f"Execution Error within Span: {e}")
                # Record the failure in the conversation history
                try:
                    error_msg = f"I encountered a system error: {str(e)}"
                    await self.graph.aupdate_state(config, {
                        "messages": [
                            AIMessage(
                                content=error_msg, 
                                additional_kwargs={
                                    "is_error": True,
                                    "execution_id": str(execution_id)
                                }
                            )
                        ]
                    })
                    # Persist error message
                    await self._save_chat_message(
                        thread_id=thread_id,
                        role="assistant",
                        content=error_msg,
                        type="error",
                        execution_id=execution_id
                    )
                except Exception as update_err:
                    logger.warning(f"Failed to record error in graph state: {update_err}")
                
                raise # Re-raise to let the controller handle the HTTP response

    @tracing(observation_type=ObservationType.AGENT)
    async def process_langgraph_chat_stream(
        self,
        thread_id: uuid.UUID,
        query: str,
        resume_payload: Optional[Dict[str, Any]] = None, # Receives the translated dict
        project_id: Optional[uuid.UUID] = None,
        dataset_ids: Optional[List[uuid.UUID]] = None
    ):
        """Streams the reasoning process using SSE."""
        execution_id = uuid.uuid4()
        
        # 1. Grab OTel Span Context
        current_otel_span = trace.get_current_span()
        span_context = current_otel_span.get_span_context()
        otel_trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
        trace_ctx: TraceContext | None = {"trace_id": otel_trace_id} if otel_trace_id else None

        with self.langfuse_client.start_as_current_observation(
            name=LANGFUSE_GRAPH_OBSERVATION_NAME + "_stream",
            as_type="agent",
            trace_context=trace_ctx
        ) as root_span:
            config: RunnableConfig = {
                "configurable": {"thread_id": str(thread_id)},
                "callbacks": [CallbackHandler(trace_context={"trace_id": root_span.trace_id, "parent_span_id": root_span.id})]
            }
            
            # Persist thread and user message
            await self._ensure_thread_exists(thread_id, project_id)

            if not resume_payload and query:
                await self._save_chat_message(thread_id=thread_id, role="user", content=query, execution_id=execution_id)
            # elif resume_payload and resume_payload.get('action') == UserFeedbackAction.MODIFY:
            #     await self._save_chat_message(thread_id=thread_id, role="user", content="[User Approved Plan]", execution_id=execution_id)

            # Yield an initial thought to let the UI know we started
            initial_chunk = StreamChunk(
                event=StreamEventType.THOUGHT, 
                data={
                    'node': 'system', 
                    'content': '🧠 Analyzing your request...' if resume_payload else '🧠 Analyzing your biological research query...'
                }
            )
            yield f"data: {initial_chunk.model_dump_json()}\n\n"

            state = await self.graph.aget_state(config)

            # 1. Check if we should resume or start fresh
            if state.next:
                logger.info(f'Thread {thread_id} is suspended at {state.next}.')
                
                if resume_payload:
                    logger.info(f"Resuming graph with payload: {resume_payload}")
                    input_state = Command(resume=resume_payload)
                elif query:
                    # If user sent a new query while suspended, treat it as feedback to modify the plan
                    logger.info(f"Resuming graph with query as feedback: {query}")
                    input_state = Command(
                        resume={
                            "action": UserFeedbackAction.MODIFY,
                            "feedback": query
                        }
                    )
                else:
                    logger.warning("Graph is suspended, but no human_feedback was provided. Cannot resume.")
                    input_state = None
            
            else:
                logger.info(f'Thread {thread_id} has no active suspension. Starting fresh.')
                active_project = None
                if project_id:
                    project_db = await self.workspace_service.get_project(project_id)
                    if project_db:
                        active_project = {
                            "project_id": str(project_db.id),
                            "project_name": project_db.name,
                            "description": project_db.description,
                            "metadata": project_db.dataset_metadata
                        }

                # 1. Fetch public dataset IDs (always included)
                public_ids = await self.workspace_service.get_public_dataset_ids()
                
                # 2. Determine project dataset IDs (fallback if none selected)
                selected_ids = dataset_ids or []
                project_ids = []
                if not selected_ids and project_id:
                    project_ids = await self.workspace_service.get_project_dataset_ids(project_id)
                
                # 3. Combine and deduplicate
                final_dataset_ids = list(set(public_ids + selected_ids + project_ids))

                active_datasets = []
                if final_dataset_ids:
                    datasets_db = await self.workspace_service.get_datasets_by_ids(final_dataset_ids)
                    
                    for ds in datasets_db:
                        genomic_files = []
                        knowledge_files = []
                        
                        for f in ds.files:
                            # Categorize the file so the LLM knows what to do with it
                            # Adjust this list based on your actual IngestionSourceType enums
                            is_genomic = is_genomic_file(f.file_name)
                            
                            agent_file = {
                                "file_id": str(f.file_id),
                                "file_name": f.file_name,
                                "file_category": "GENOMIC" if is_genomic else "KNOWLEDGE",
                                "file_type": str(f.file_type),
                                "rustfs_uri": f.rustfs_uri,
                                "local_content": None
                            }
                            
                            if is_genomic:
                                genomic_files.append(agent_file)
                            else:
                                knowledge_files.append(agent_file)
                                
                        active_datasets.append({
                            "dataset_id": str(ds.id),
                            "dataset_name": ds.name,
                            "source": "SYSTEM_LIBRARY" if ds.is_public else "USER_WORKSPACE",
                            "genomic_files": genomic_files,
                            "knowledge_files": knowledge_files
                        })
                # Build initial state
                input_state = {
                    "query": query,
                    "messages": [HumanMessage(content=query)],
                    "iteration_count": 0,
                    "execution_id": execution_id,
                    "start_time": time.time(),
                    "plan": [],            
                    "past_steps": [],      
                    "final_answer": "",
                    "active_project": active_project, 
                    "active_datasets": active_datasets
                }

            # Filter for specific nodes we want to stream thoughts from
            REASONING_NODES = {
                AgentGraphNode.PLANNER, 
                AgentGraphNode.EXECUTOR, 
                AgentGraphNode.ROUTER, 
                AgentGraphNode.SYNTHESIZER
            }

            async def _yield_interrupt_payload(status_flag: dict):
                """Helper to extract and yield the interrupt data from the LATEST state."""
                state = await self.graph.aget_state(config)
                
                interrupt_data = {}
                if state.tasks:
                    for task in state.tasks:
                        if task.interrupts:
                            interrupt_data = task.interrupts[0].value
                            break
                
                if interrupt_data:
                    thought_chunk = StreamChunk(
                        event=StreamEventType.THOUGHT, 
                        data={
                            'node': 'planner', 
                            'content': 'I have drafted a research plan. Please review it below to proceed.'
                        }
                    )
                    yield f"data: {thought_chunk.model_dump_json()}\n\n"
                    
                    interrupt_chunk = StreamChunk(
                        event=StreamEventType.INTERRUPT, 
                        data={
                            'next_nodes': state.next, 
                            'interrupt_payload': interrupt_data
                        }
                    )
                    yield f"data: {interrupt_chunk.model_dump_json()}\n\n"
                    
                    status_flag["interrupted"] = True
                    return 
                
                if state.next:
                    empty_interrupt_chunk = StreamChunk(
                        event=StreamEventType.INTERRUPT, 
                        data={
                            'next_nodes': state.next, 
                            'interrupt_payload': {}
                        }
                    )
                    yield f"data: {empty_interrupt_chunk.model_dump_json()}\n\n"
                    
                    status_flag["interrupted"] = True
                    return

                status_flag["interrupted"] = False
                return

            try:
                if input_state is not None:
                    async for event in self.graph.astream_events(input_state, config, version="v2"):
                        kind = event["event"]
                        name = event["name"]

                        # 0. Show progress as we enter nodes
                        if kind == EventKind.CHAIN_START and name in REASONING_NODES:
                            chunk = StreamChunk(
                                event=StreamEventType.THOUGHT, 
                                data={
                                    'node': name, 
                                    'content': f'Entering {name} node...'
                                }
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"

                        # 1. Thoughts & Node Transitions
                        if kind == EventKind.CHAIN_END and name in REASONING_NODES:
                            output = event["data"].get("output")
                            if output:
                                content = None

                                # Case A: It's a LangGraph Command object
                                if hasattr(output, "update") and isinstance(output.update, dict):
                                    content = (
                                        output.update.get("final_answer") or 
                                        (output.update.get("messages", [{}])[-1].content if output.update.get("messages") else None)
                                    )

                                # Case B: It's a standard dictionary
                                elif isinstance(output, dict):
                                    content = output.get("final_answer") or output.get("content")

                                # Case C: It's a LangChain Message object
                                elif hasattr(output, "content"):
                                    content = output.content

                                if content:
                                    chunk = StreamChunk(
                                        event=StreamEventType.THOUGHT, 
                                        data={
                                            'node': name, 
                                            'content': str(content)
                                        }
                                    )
                                    yield f"data: {chunk.model_dump_json()}\n\n"

                        # 2. Tool Executions
                        elif kind == EventKind.TOOL_START:
                            chunk = StreamChunk(
                                event=StreamEventType.TOOL_START, 
                                data={
                                    'tool': name, 
                                    'inputs': event['data'].get('input')
                                }
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"
                            
                        elif kind == EventKind.TOOL_END:
                            tool_output = event["data"].get("output")
                            # Stringify output safely for SSE stream
                            safe_output = str(tool_output)[:1000] if tool_output is not None else "No output."
                            
                            chunk = StreamChunk(
                                event=StreamEventType.TOOL_END, 
                                data={
                                    'tool': name, 
                                    'output': safe_output
                                }
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"

                        # 3. Final Answer (from Synthesizer)
                        if kind == EventKind.CHAIN_END and name == AgentGraphNode.SYNTHESIZER:
                            output = event["data"].get("output")
                            final_answer = None
                            
                            if isinstance(output, BaseModel):
                                final_answer = getattr(output, "final_answer", None)
                            elif isinstance(getattr(output, "update", None), dict):
                                final_answer = getattr(output, "update").get("final_answer")
                            elif isinstance(output, dict):
                                final_answer = output.get("final_answer")

                            if final_answer:
                                chunk = StreamChunk(
                                    event=StreamEventType.ANSWER, 
                                    data=final_answer
                                )
                                yield f"data: {chunk.model_dump_json()}\n\n"

                                await self._save_chat_message(
                                    thread_id=thread_id,
                                    role="assistant",
                                    content=final_answer,
                                    type="answer",
                                    execution_id=execution_id
                                )

                # 1. Initialize the status dictionary
                interrupt_status = {"interrupted": False}

                # 2. Consume the generator using async for
                async for chunk in _yield_interrupt_payload(interrupt_status):
                    yield chunk

                # 3. Check the flag we just set inside the helper
                if not interrupt_status["interrupted"]:
                    # Standard completion: Only send DONE if we didn't hit an interrupt
                    # final_state = await self.graph.aget_state(config)
                    # absolute_final_answer = final_state.values.get("final_answer")
                    
                    # if absolute_final_answer:
                    #     # Stream the answer if it was missed (e.g. from Planner bypassing Synthesizer)
                    #     chunk = StreamChunk(
                    #         event=StreamEventType.ANSWER, 
                    #         data=absolute_final_answer
                    #     )
                    #     yield f"data: {chunk.model_dump_json()}\n\n"

                    #     await self._save_chat_message(
                    #         thread_id=thread_id,
                    #         role="assistant",
                    #         content=absolute_final_answer,
                    #         type="answer",
                    #         execution_id=execution_id
                    #     )
            
                    chunk = StreamChunk(
                        event=StreamEventType.DONE, 
                        data={}
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

            except GraphInterrupt as e:
                # Catch actual LangGraph suspensions cleanly!
                logger.info(f"Graph suspended natively. Yielding interrupt payload.")
                
                exc_status = {"interrupted": False}
                async for chunk in _yield_interrupt_payload(exc_status):
                    yield chunk
                    
            except Exception as e:
                # Catch REAL errors (e.g., API keys missing, DB connection dropped, etc.)
                logger.error(f"Streaming Error: {e}")
                chunk = StreamChunk(event=StreamEventType.ERROR, data=str(e))
                yield f"data: {chunk.model_dump_json()}\n\n"
    
    # async def resume_graph(self, thread_id: uuid.UUID, feedback: Any):
    #     """Resumes a suspended graph execution by saving feedback to state."""
    #     config: RunnableConfig = {"configurable": {"thread_id": str(thread_id)}}
        
    #     try:
    #         # 1. Inspect state to confirm where we are suspended
    #         state = await self.graph.aget_state(config)
    #         logger.info(f"[Resume] Thread {thread_id} suspended at {state.next}. Tasks: {len(state.tasks) if state.tasks else 0}")
            
    #         # 2. Update state with the feedback so the next stream can use it to resume
    #         await self.graph.aupdate_state(config, {"_resume_value": feedback})
            
    #         return {"status": "resumed", "thread_id": thread_id}
    #     except Exception as e:
    #         logger.error(f"[Resume] Failed for thread {thread_id}: {e}")
    #         raise e

    async def get_conversation_history(self, thread_id: uuid.UUID) -> dict:
        """Retrieves the conversation history from the chat_messages table."""
        async with langgraph_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, role, content, type, execution_id, chat_metadata FROM chat_messages WHERE thread_id = %s ORDER BY created_at ASC",
                (thread_id,)
            )
            rows = await cursor.fetchall()

            formatted_messages = []
            for row in rows:
                formatted_messages.append({
                    "id": str(row["id"]),
                    "role": row["role"],
                    "content": row["content"],
                    "type": row["type"],
                    "execution_id": row["execution_id"]
                })            
            return {
                "thread_id": thread_id,
                "messages": formatted_messages,
                "rag_results": [], 
                "tool_results": [],
                "web_results": []
            }
        
    async def _ensure_thread_exists(self, thread_id: uuid.UUID, project_id: Optional[uuid.UUID] = None):
        async with langgraph_connection_pool.connection() as conn:
            # Check if exists
            cursor = await conn.execute("SELECT id FROM chat_threads WHERE thread_id = %s", (thread_id,))
            if not await cursor.fetchone():
                await conn.execute(
                    "INSERT INTO chat_threads (thread_id, user_id, project_id) VALUES (%s, %s, %s)",
                    (thread_id, SYSTEM_OWNER_ID, project_id)
                )

    async def _save_chat_message(self, thread_id: uuid.UUID, role: str, content: str, type: str = "answer", execution_id: Optional[uuid.UUID] = None, chat_metadata: Optional[dict] = None):
        async with langgraph_connection_pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO chat_messages (thread_id, role, content, type, execution_id, chat_metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (thread_id, role, content, type, execution_id, json.dumps(chat_metadata) if chat_metadata else None)
            )

    async def _generate_and_update_title(self, thread_id: uuid.UUID, first_query: str):
        """Generates a short title based on the first query and updates the thread."""
        try:
            # Simple prompt for title generation
            prompt = f"Generate a very short, concise title (max 5 words) for a biological research conversation that starts with: '{first_query}'"
            # Use secondary model for speed
            llm = self.llm_service.get_structured_secondary_model(ThreadTitleOutput)
            response = await llm.ainvoke(prompt)
            title = response.title.strip().strip('"')
            
            async with langgraph_connection_pool.connection() as conn:
                await conn.execute(
                    "UPDATE chat_threads SET title = %s WHERE thread_id = %s",
                    (title, thread_id)
                )
        except Exception as e:
            logger.warning(f"Failed to generate title: {e}")
            
    async def _consolidate_sources(self, raw_sources: list) -> List[RAGSourceItem]:
        """Groups raw chunks by source_file to return a clean summary."""
        unique_sources = {}
        
        for source in raw_sources:
            file_name = source.get("source_file", "Unknown")
            score = source.get("score", 0.0)
            
            if file_name not in unique_sources:
                unique_sources[file_name] = RAGSourceItem(
                    source_file=file_name,
                    chunks_used=1,
                    highest_score=score
                )
            else:
                unique_sources[file_name].chunks_used += 1
                current_max = unique_sources[file_name].highest_score or 0.0
                unique_sources[file_name].highest_score = max(current_max, score)
                
        return list(unique_sources.values())
