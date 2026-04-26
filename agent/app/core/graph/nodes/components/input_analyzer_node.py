import asyncio
import time
from langfuse import observe
from loguru import logger
from typing import Any, Dict, List, Literal, Optional

from app.common.constants import ObservationType, UploadedFileType
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.configs.settings.settings import get_settings
from app.utils.document_processor import DocumentProcessor
from app.core.graph.state.agent_state import AgentState
from app.core.prompts.input_analyzer_prompts import (
    INPUT_ANALYZER_GENOMIC_FILE_NOTE,
    INPUT_ANALYZER_MASSIVE_FILE_NOTE,
    INPUT_ANALYZER_FILE_CONTEXT_HEADER
)
from langchain_core.messages import SystemMessage
from langchain_core.documents import Document
from langgraph.types import Command


# Wrap in factory method
def make_input_analyzer_node(document_processor: DocumentProcessor):
    @tracing(observation_type=ObservationType.CHAIN)
    async def input_analyzer(state: AgentState) -> Command[
        Literal[AgentGraphNode.ROUTER]
    ]:
        settings = get_settings()
        start_time = time.time()

        logger.debug("========== [Input Analyzer Node] ==========")
        logger.debug(f"State keys: {list(state.keys())}")
        logger.debug(f"Query: {state.get('query')}")

        files = state.get("uploaded_files", [])
        logger.debug(f"Uploaded files count: {len(files)}")

        file_context = ""
        ephemeral_chunks = []

        if files:
            for f in files:
                file_name = f.get('file_name', 'Unknown')
                file_type = f.get('file_type', 'unknown')   # Trusted classification from initial_state
                file_path = f.get('file_path')
                local_content = f.get('local_content')
                rustfs_uri = f.get('rustfs_uri')
                description = f.get('description', '')

                # 1. HEAVY GENOMIC DATASETS (Already in S3)
                if file_type == UploadedFileType.GENOMIC_DATASET or rustfs_uri:
                    logger.debug(f"🧬 {file_name} is a genomic dataset. Passing S3 URI to state.")
                    file_context += INPUT_ANALYZER_GENOMIC_FILE_NOTE.format(
                        file_name=file_name,
                        rustfs_uri=rustfs_uri,
                        description=description
                    )
                
                # 2. LOCAL TEXT / SEQUENCES / SAMPLES
                elif local_content:
                    logger.debug(f"📝 {file_name} has local content available. Injecting directly.")
                    file_context += f"--- Start of Content: {file_name} (Type: {file_type}) ---\nDescription: {description}\n{local_content}\n--- End of {file_name} ---\n\n"
                    
                    doc = Document(
                        page_content=local_content,
                        metadata={"source": file_name, "type": file_type}
                    )
                    ephemeral_chunks.append(doc)
                    
                # 3. DOCUMENTS REQUIRING OCR/DOCLING
                elif file_type == UploadedFileType.CONTEXT_DOCUMENT and file_path:
                    logger.debug(f"Parsing uploaded file with Docling: {file_name}")
                    try:
                        # Process heavy files in background thread to prevent blocking 
                        chunks = await asyncio.to_thread(
                            document_processor.process_and_get_chunks, file_path
                        )
                        parsed_text = "\n".join([chunk.page_content for chunk in chunks])

                        if len(parsed_text) > settings.gemini_max_input_token:
                            logger.warning(f"⚠️ {file_name} is massive. Saving to RAM for local BM25 search.")
                            ephemeral_chunks.extend(chunks)
                            file_context += INPUT_ANALYZER_MASSIVE_FILE_NOTE.format(
                                file_name=file_name
                            )
                        else:    
                            logger.debug(f"📄 {file_name} parsed successfully. Injecting directly.")
                            file_context += f"--- Start of Content: {file_name} (Type: {file_type}) ---\n{parsed_text}\n--- End of {file_name} ---\n\n"

                    except Exception as e:
                        logger.exception(f"Failed to parse uploaded file {file_name}")
                        file_context += f"--- Start of Content: {file_name} ---\n[Error: Could not extract text from this file.]\n--- End of {file_name} ---\n\n"
                
                # Failsafe
                else:
                    logger.warning(f"❓ File {file_name} lacked expected fields for type '{file_type}'.")
            if file_context:
                file_context = f"{INPUT_ANALYZER_FILE_CONTEXT_HEADER}{file_context}"
                logger.debug("Successfully extracted file content.")
        else:
            logger.debug("No uploaded files provided")

        current_iter = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations")

        logger.debug(f"Iteration count: {current_iter}")
        logger.debug(f"Max iterations: {max_iter}")

        elapsed = int((time.time() - start_time) * 1000)
        logger.debug(f"Input Analyzer execution time: {elapsed} ms")

        return Command(
            goto=AgentGraphNode.ROUTER,
            update={
                # System instructions/context about files for the Router
                "file_context": file_context, # Store in separate field
                "uploaded_chunks": ephemeral_chunks,

                # Reset standard ReAct loop variables for the new run
                "tool_results": [],
                "web_results": [],
                "rag_results": [],
                "iteration_count": 0,
                "required_tools": []
            }
        )

    return input_analyzer