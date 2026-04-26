import asyncio
import gzip
import os
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional, AsyncContextManager, cast
import uuid

import aioboto3
import aiofiles
from fastapi import HTTPException, UploadFile
from langfuse import Langfuse, propagate_attributes
from langfuse.types import TraceContext
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from loguru import logger
from opentelemetry import trace
from types_aiobotocore_s3 import S3Client

from app.services.ingestion.file_ingestion_service import FileIngestionService
from app.utils.files.files_classifier import is_genomic_file, is_knowledge_file
from app.common.constants import GENOMIC_EXTENSIONS, LANGFUSE_GRAPH_OBSERVATION_NAME, LANGGRAPH_STATE_MAX_ITERATIONS, UploadedFileType
from app.configs.settings.settings import get_settings
from app.services.llm.llm_service import LLMService
from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem


class AgentService:
    def __init__(
        self,
        graph: CompiledStateGraph,
        file_ingestion_service: FileIngestionService,
        llm_service: LLMService,
        langfuse_client: Langfuse
    ):
        self.graph = graph
        self.file_ingestion_service = file_ingestion_service
        self.llm_service = llm_service
        self.langfuse_client = langfuse_client
        self.settings = get_settings()

    async def process_langgraph_chat(
        self,
        thread_id: uuid.UUID,
        query: str,
        files: Optional[List[UploadFile]] = None,
        project_name: Optional[str] = None,
        dataset_name: Optional[str] = None
    ) -> AgentResponse:
        """Handles file saving, graph execution, and source consolidation."""
        start_time = time.time()
        callbacks = []

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
            try:
                with propagate_attributes(
                    session_id=str(thread_id),
                    tags=["agent_chat"]
                ):
                    
                    # Because we are inside the context, initializing the handler here 
                    # automatically binds it to the OTel trace ID!
                    lf_handler = CallbackHandler()
                    callbacks.append(lf_handler)
                    
                    # 4. Delegate File Processing to the sub-service
                    preprocessed_files = []
                    if files:
                        preprocessed_files = await self.file_ingestion_service.process_uploads(files)
                        
                    config: RunnableConfig = {
                        "configurable": {
                            "thread_id": str(thread_id),
                            "sync_file_callback": self.file_ingestion_service.wait_for_file_readiness
                        },
                        "callbacks": callbacks 
                    }
                    
                    # Retrieve existing state
                    existing_state = await self.graph.aget_state(config)

                    # Hierarchy Persistence Logic:
                    # Priority: 1. Explicit Argument -> 2. Existing State -> 3. "Default"
                    final_project = project_name or (existing_state.values.get("project_name") if (existing_state and existing_state.values) else None) or "Default Project"
                    final_dataset = dataset_name or (existing_state.values.get("dataset_name") if (existing_state and existing_state.values) else None) or "Default Dataset"

                    previous_files = existing_state.values.get("uploaded_files", []) if (existing_state and existing_state.values) else []

                    # Build initial state
                    initial_state = {
                        "query": query,
                        "messages": [HumanMessage(content=query)],      
                        "uploaded_files": previous_files + preprocessed_files, 
                        "project_name": final_project,
                        "dataset_name": final_dataset,
                        "iteration_count": 0,
                        "max_iterations": LANGGRAPH_STATE_MAX_ITERATIONS 
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
                            "project": final_project,
                            "dataset": final_dataset
                        },
                        output={"final_answer": agent_response.answer}
                    )

                    return agent_response
            except Exception as e:
                # 🌟 Log the error BEFORE the 'with' block exits
                logger.error(f"Execution Error within Span: {e}")
                raise # Re-raise to let the controller handle the HTTP response


    async def get_conversation_history(self, thread_id: uuid.UUID) -> dict:
        """Retrieves the conversation history and execution data from the LangGraph checkpointer."""
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

        # 1. Extract the custom execution lists from your AgentState
        rag_results = state_values.get("rag_results", [])
        tool_results = state_values.get("tool_results", [])
        web_results = state_values.get("web_results", [])

        # 2. Format standard chat messages for the API response
        raw_messages = state_values.get("messages", [])
        formatted_messages = []
        
        for msg in raw_messages:
            msg_type = msg.type # Usually 'human', 'ai', 'tool', etc.
            
            # We only map human and AI messages here because your custom 
            # tool_results array already holds the beautifully structured tool data
            if msg_type in ["human", "ai"]:
                formatted_messages.append({
                    "role": "user" if msg_type == "human" else "assistant",
                    "content": msg.content
                })

        # 3. Return the rich payload
        return {
            "thread_id": thread_id,
            "messages": formatted_messages,
            "rag_results": rag_results,
            "tool_results": tool_results,
            "web_results": web_results,
            "summary": state_values.get("summary", "") # Optional: grab the rolling summary too!
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

