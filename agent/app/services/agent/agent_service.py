import gzip
import os
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional, AsyncContextManager, cast
import uuid

import aioboto3
from fastapi import HTTPException, UploadFile
from langfuse import Langfuse, propagate_attributes
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from loguru import logger
from opentelemetry import trace
from types_aiobotocore_s3 import S3Client

from app.configs.settings.settings import get_settings
from app.services.llm.llm_service import LLMService
from app.utils.files.files_classifier import classify_upload_with_llm
from app.utils.files.files_validator import extract_file_sample, validate_genomic_file, validate_knowledge_file
from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem


class AgentService:
    def __init__(
        self,
        graph: CompiledStateGraph,
        rustfs_session: aioboto3.Session,
        llm_service: LLMService,
        langfuse_client: Langfuse
    ):
        self.graph = graph
        self.rustfs_session = rustfs_session
        self.llm_service = llm_service
        self.langfuse_client = langfuse_client
        self.settings = get_settings()

    async def process_langgraph_chat(
        self,
        thread_id: uuid.UUID,
        query: str,
        files: Optional[List[UploadFile]] = None
    ) -> AgentResponse:
        """Handles file saving, graph execution, and source consolidation."""
        start_time = time.time()
        uploaded_files_meta = []
        callbacks = []

        # 1. Grab OTel Span Context
        current_otel_span = trace.get_current_span()
        span_context = current_otel_span.get_span_context()
        otel_trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
        
        # 2. Create the trace context mapping
        trace_ctx = {"trace_id": otel_trace_id} if otel_trace_id else None
            
        # 3. Call explicitly (No **kwargs unpacking). 
        # This allows Pylance to see as_type="span" and pick the correct overload.
        with self.langfuse_client.start_as_current_observation(
            name="sugarcane_agent_execution",
            as_type="span",
            trace_context=trace_ctx  # type: ignore 
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


                    if files:
                        temp_dir = Path("/tmp/sugarcane_uploads")
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        
                        for file in files:
                            filename = file.filename or f"unnamed_file_{uuid.uuid4().hex[:6]}"
                            file_id = str(uuid.uuid4())
                            safe_filename = f"{file_id}_{filename}"
                            temp_path = temp_dir / safe_filename
                            
                            with temp_path.open("wb") as buffer:
                                shutil.copyfileobj(file.file, buffer)

                            try:
                                try:
                                    snippet = extract_file_sample(temp_path, max_lines=5) 
                                except Exception as e:
                                    logger.warning(f"Failed to read snippet from {filename}: {e}")
                                    snippet = ""

                                # classification LLM gets traced via callbacks
                                classification = await classify_upload_with_llm(
                                    filename, query, snippet, self.llm_service, callbacks=callbacks
                                )

                                # --- PATH A: GENOMIC PIPELINE ---
                                if classification == "genomic":
                                    is_valid, error_msg = validate_genomic_file(temp_path, filename)
                                    if not is_valid:
                                        raise HTTPException(400, f"Validation Failed for {filename}: {error_msg}")
                                    
                                    file_size_bytes = temp_path.stat().st_size
                                    if file_size_bytes < 10 * 1024: 
                                        raw_sequence = temp_path.read_text(encoding="utf-8", errors="ignore").strip()
                                        uploaded_files_meta.append({
                                            "file_id": file_id, "file_name": filename, "file_type": "raw_sequence",
                                            "local_content": raw_sequence, "description": "Pass local_content to tools."
                                        })
                                    else:
                                        rustfs_uri, final_name = await self._compress_and_upload_to_s3(temp_path, filename, self.rustfs_session)
                                        uploaded_files_meta.append({
                                            "file_id": file_id, "file_name": final_name, "rustfs_uri": rustfs_uri,
                                            "file_type": "genomic_dataset", "description": "Pass S3 URI to tools."
                                        })

                                # --- PATH B: KNOWLEDGE DOCUMENT ---
                                elif classification == "knowledge":
                                    is_valid, error_msg = validate_knowledge_file(temp_path, filename)
                                    if not is_valid:
                                        raise HTTPException(400, f"Validation Failed for {filename}: {error_msg}")
                                    
                                    text_content = temp_path.read_text(encoding="utf-8", errors="ignore")
                                    uploaded_files_meta.append({
                                        "file_id": file_id, "file_name": filename, "file_type": "context_document",
                                        "local_content": text_content[:100000], "description": "Read 'local_content'."
                                    })

                                # --- PATH C: EXPLANATION/SAMPLE ONLY ---
                                elif classification == "sample_only":
                                    sample_text = extract_file_sample(temp_path, max_lines=50)
                                    uploaded_files_meta.append({
                                        "file_id": file_id, "file_name": filename, "file_type": "context_document",
                                        "local_content": f"Interpret this file (first 50 lines):\n\n{sample_text}"
                                    })

                                # --- PATH D: REJECT ---
                                else:
                                    raise HTTPException(400, f"File type rejected for {filename}.")

                            finally:
                                if temp_path.exists():
                                    temp_path.unlink()
                                

                    config: RunnableConfig = {
                        "configurable": {
                            "thread_id": str(thread_id)
                        },
                        "callbacks": callbacks 
                    }
                    
                    existing_state = await self.graph.aget_state(config)
                    previous_files = existing_state.values.get("uploaded_files", []) if (existing_state and existing_state.values) else []

                    initial_state = {
                        "query": query,
                        "messages": [HumanMessage(content=query)],      
                        "uploaded_files": previous_files + uploaded_files_meta, 
                        "iteration_count": 0,
                        "max_iterations": 3 
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

                    # Optionally log the final output to the root span
                    root_span.set_trace_io(
                        input={"user_query": query},
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

    async def _compress_and_upload_to_s3(self, temp_path: Path, original_filename: str, s3_context: aioboto3.Session) -> tuple[str, str]:
        """Compresses file if needed, uploads to RustFS via aioboto3, and returns the S3 URI and new filename."""
        bucket_name = "sugarcane-genomes"
        file_id = str(uuid.uuid4())
        
        is_already_gz = temp_path.name.endswith(".gz")
        upload_path = temp_path
        final_filename = original_filename

        # Compress on the fly if user uploaded raw text
        if not is_already_gz:
            final_filename = f"{original_filename}.gz"
            compressed_temp_path = temp_path.with_suffix(temp_path.suffix + '.gz')
            
            logger.info(f"Compressing {original_filename} before S3 upload...")
            with open(temp_path, 'rb') as f_in:
                with gzip.open(compressed_temp_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            upload_path = compressed_temp_path 

        safe_filename = f"{file_id}_{final_filename}"
        
        # Use aioboto3's native async upload_file (highly efficient for disk paths)
        logger.info(f"Uploading {safe_filename} to RustFS bucket: {bucket_name}")

        rustfs_client = cast(
            AsyncContextManager[S3Client],
            self.rustfs_session.client(
                "s3",
                endpoint_url=self.settings.rustfs_endpoint_url,
                aws_access_key_id=self.settings.rustfs_access_key_id,
                aws_secret_access_key=self.settings.rustfs_secret_access_key,
                region_name=self.settings.rustfs_region_name
            )
        )

        async with rustfs_client as s3_client:
            await s3_client.upload_file(str(upload_path), bucket_name, safe_filename)
        
        # Clean up the compressed copy if we created one
        if not is_already_gz and upload_path.exists():
            upload_path.unlink()
            
        return f"s3://{bucket_name}/{safe_filename}", final_filename
    
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

