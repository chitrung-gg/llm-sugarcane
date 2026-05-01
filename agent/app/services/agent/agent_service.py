import asyncio
import os
import time
from typing import Dict, List, Optional, AsyncContextManager, cast
import uuid

import aioboto3
from fastapi import HTTPException
from langfuse import Langfuse, propagate_attributes
from langfuse.types import TraceContext
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langfuse.langchain import CallbackHandler
from loguru import logger
from opentelemetry import trace
import json

from app.utils.observability.tracing import tracing
from app.services.workspace.workspace_service import WorkspaceService
from app.common.constants import LANGFUSE_GRAPH_OBSERVATION_NAME, LANGGRAPH_STATE_MAX_ITERATIONS, ObservationType, SYSTEM_OWNER_ID
from app.services.llm.llm_service import LLMService
from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem, ThreadTitleOutput
from app.configs.storage.databases import langgraph_connection_pool


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

                    # Build initial state
                    initial_state = {
                        "query": query,
                        "messages": messages_to_add,      
                        "active_project_name": active_project_name,
                        "active_datasets": active_datasets,
                        "iteration_count": 0,
                        "execution_id": execution_id
                    }

                    # Langgraph executes entirely within the Langfuse root_span
                    final_state = await self.graph.ainvoke(initial_state, config=config)

                    # Consolidate Sources & Build Response
                    raw_sources = final_state.get("sources_used", [])
                    consolidated_sources = await self._consolidate_sources(raw_sources)
                    process_time = time.time() - start_time

                    thoughts = []
                    for msg in final_state.get("messages", []):
                        if msg.type == "ai" and msg.additional_kwargs.get("is_thought") and msg.additional_kwargs.get("execution_id") == str(execution_id):
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


    async def get_conversation_history(self, thread_id: uuid.UUID) -> dict:
        """Retrieves the conversation history from the chat_messages table."""
        async with langgraph_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, role, content, type, execution_id, metadata FROM chat_messages WHERE thread_id = %s ORDER BY created_at ASC",
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

    async def _save_chat_message(self, thread_id: uuid.UUID, role: str, content: str, type: str = "answer", execution_id: Optional[uuid.UUID] = None, metadata: Optional[dict] = None):
        async with langgraph_connection_pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO chat_messages (thread_id, role, content, type, execution_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (thread_id, role, content, type, execution_id, json.dumps(metadata) if metadata else None)
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
