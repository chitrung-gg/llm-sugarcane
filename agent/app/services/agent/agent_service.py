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

from app.utils.observability.tracing import tracing
from app.services.workspace.workspace_service import WorkspaceService
from app.common.constants import LANGFUSE_GRAPH_OBSERVATION_NAME, LANGGRAPH_STATE_MAX_ITERATIONS, ObservationType
from app.configs.settings.settings import get_settings
from app.services.llm.llm_service import LLMService
from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem


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
        self.settings = get_settings()


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

                    agent_response = AgentResponse(
                        thread_id=thread_id,
                        answer=final_state.get("final_answer", "No answer generated."),
                        rag_sources=consolidated_sources, 
                        web_results=final_state.get("web_results", []),
                        tool_executions=final_state.get("tool_results", []),
                        execution_time=process_time
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
                except Exception as update_err:
                    logger.warning(f"Failed to record error in graph state: {update_err}")
                
                raise # Re-raise to let the controller handle the HTTP response


    async def get_conversation_history(self, thread_id: uuid.UUID) -> dict:
        """Retrieves the conversation history from the LangGraph checkpointer."""
        config: RunnableConfig = {
            "configurable": {
                "thread_id": str(thread_id)
            }
        }

        # Retrieve the latest state snapshot for this thread
        state_snapshot = await self.graph.aget_state(config)

        # If the thread doesn't exist or has no state, return empty structure
        if not state_snapshot or not state_snapshot.values:
            return {
                "thread_id": thread_id, 
                "messages": [],
                "rag_results": [],
                "tool_results": [],
                "web_results": []
            }

        state_values = state_snapshot.values
        formatted_messages = []
        for msg in state_values.get("messages", []):
            if msg.type in ["human", "ai"]:
                msg_data = {
                    "role": "user" if msg.type == "human" else "assistant",
                    "content": msg.content
                }
                
                # Expose metadata for the UI (e.g. thoughts, errors)
                if msg.type == "ai":
                    msg_data["execution_id"] = msg.additional_kwargs.get("execution_id")
                    if msg.additional_kwargs.get("is_thought"):
                        msg_data["type"] = "thought"
                    elif msg.additional_kwargs.get("is_error"):
                        msg_data["type"] = "error"
                    else:
                        msg_data["type"] = "answer"
                
                formatted_messages.append(msg_data)

        return {
            "thread_id": thread_id,
            "messages": formatted_messages,
            "rag_results": state_values.get("rag_results", []),
            "tool_results": state_values.get("tool_results", []),
            "web_results": state_values.get("web_results", []),
            "summary": state_values.get("summary", "")
        }
        
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
