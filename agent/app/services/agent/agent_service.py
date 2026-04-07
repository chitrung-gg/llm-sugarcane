import gzip
import os
from pathlib import Path
import shutil
import time
from typing import List, Optional
import uuid
from botocore.client import BaseClient

from fastapi import HTTPException, UploadFile
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langchain_core.messages import HumanMessage
from loguru import logger

from app.services.llm.llm_service import LLMService
from app.utils.files.files_classifier import classify_upload_with_llm
from app.utils.files.files_validator import extract_file_sample, validate_genomic_file, validate_knowledge_file
from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem
from app.core.tools.genome_tool import list_genome_files
from app.schemas.agent.agent_request import AgentRequest

class AgentService:
    def __init__(
        self,
        graph: CompiledStateGraph,
        rustfs_client: BaseClient,
        llm_service: LLMService
    ):
        self.graph = graph
        self.rustfs_client = rustfs_client
        self.llm_service = llm_service

    async def process_langgraph_chat(
        self,
        thread_id: uuid.UUID,
        query: str,
        files: Optional[List[UploadFile]] = None
    ) -> AgentResponse:
        """Handles file saving, graph execution, and source consolidation."""
        start_time = time.time()
        uploaded_files_meta = []

        # 1. Handle File Upload
        if files:
            temp_dir = Path("/tmp/sugarcane_uploads")
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                # Resolve the str | None type error with a fallback
                filename = file.filename or f"unnamed_file_{uuid.uuid4().hex[:6]}"
                
                file_id = str(uuid.uuid4())
                safe_filename = f"{file_id}_{filename}"
                temp_path = temp_dir / safe_filename
                
                # Securely spool the upload to local disk first
                with temp_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                try:
                    # AI Classification
                    classification = await classify_upload_with_llm(filename, query, self.llm_service)

                    # --- PATH A: GENOMIC PIPELINE ---
                    if classification == "genomic":
                        is_valid, error_msg = validate_genomic_file(temp_path, filename)
                        if not is_valid:
                            raise HTTPException(400, f"Validation Failed for {filename}: {error_msg}")
                        
                        rustfs_uri, final_name = await self._compress_and_upload_to_s3(temp_path, filename, self.rustfs_client)
                        
                        uploaded_files_meta.append({
                            "file_id": file_id,
                            "file_name": final_name,
                            "rustfs_uri": rustfs_uri,
                            "file_type": "genomic_dataset",
                            "description": "A heavy genomic dataset stored in RustFS. Pass its S3 URI to tools."
                        })

                    # --- PATH B: KNOWLEDGE DOCUMENT ---
                    elif classification == "knowledge":
                        is_valid, error_msg = validate_knowledge_file(temp_path, filename)
                        if not is_valid:
                            raise HTTPException(400, f"Validation Failed for {filename}: {error_msg}")
                        
                        text_content = temp_path.read_text(encoding="utf-8", errors="ignore")
                        
                        uploaded_files_meta.append({
                            "file_id": file_id,
                            "file_name": filename,
                            "file_path": str(temp_path), 
                            "file_type": "context_document",
                            "local_content": text_content[:100000] 
                        })

                    # --- PATH C: EXPLANATION/SAMPLE ONLY ---
                    elif classification == "sample_only":
                        sample_text = extract_file_sample(temp_path, max_lines=50)
                        
                        uploaded_files_meta.append({
                            "file_id": file_id,
                            "file_name": filename,
                            "file_type": "context_document",
                            "local_content": f"The user wants you to interpret this file. Here are the first 50 lines:\n\n{sample_text}"
                        })

                    # --- PATH D: REJECT ---
                    else:
                        raise HTTPException(400, f"File type rejected for {filename}.")

                finally:
                    # Clean up the temporary file for THIS iteration
                    if temp_path.exists():
                        temp_path.unlink()
                    
        # 2. Initial AgentState
        initial_state = {
            "query": query,
            "messages": [HumanMessage(content=query)],      # Add users messages
            "uploaded_files": uploaded_files_meta, 
            "iteration_count": 0,
            "max_iterations": 3 
        }

        # 3. Configure the checkpointer to load/save to a specific thread
        config: RunnableConfig = {
            "configurable": {
                "thread_id": str(thread_id)
            }
        }

        # 4. Execute Graph with the config
        final_state = await self.graph.ainvoke(initial_state, config=config)

        # 5. Consolidate Sources
        raw_sources = final_state.get("sources_used", [])
        consolidated_sources = await self._consolidate_sources(raw_sources)
        process_time = time.time() - start_time

        # 6. Build and Return Response
        return AgentResponse(
            thread_id=thread_id,
            answer=final_state.get("final_answer", "No answer generated."),
            rag_sources=consolidated_sources, 
            tool_executions=final_state.get("tool_results", []),
            execution_time=process_time
        )

    async def _compress_and_upload_to_s3(self, temp_path: Path, original_filename: str, s3_client: BaseClient) -> tuple[str, str]:
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

