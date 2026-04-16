import time
from loguru import logger
from typing import Dict, Any, Literal

from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.configs.settings.settings import get_settings
from app.utils.document_processor import DocumentProcessor
from app.core.graph.state.agent_state import AgentState
from langchain_core.messages import SystemMessage
from langchain_core.documents import Document
from langgraph.types import Command


# Wrap in factory method
def make_input_analyzer_node(document_processor: DocumentProcessor):
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
                file_name = f.get('file_name')
                file_path = f.get('file_path')
                file_type = f.get('file_type')
                local_content = f.get('local_content')
                rustfs_uri = f.get('rustfs_uri')
                description = f.get('description', '')

                # CASE 1: Small text file/sequence (Already loaded into memory)
                if local_content:
                    logger.debug(f"📄 {file_name} is small text/sequence. Injecting directly.")
                    file_context += f"--- Start of Content: {file_name} (Type: {file_type}) ---\nDescription: {description}\n{local_content}\n--- End of {file_name} ---\n\n"
                    
                    # We also wrap it in a Document just in case RAG attempts to search it
                    doc = Document(
                        page_content=local_content,
                        metadata={"source": file_name, "type": file_type}
                    )
                    ephemeral_chunks.append(doc)
                    
                # CASE 2: Standard Document (Needs Docling parsing)
                elif file_path:
                    logger.debug(f"Parsing uploaded file with Docling: {file_name}")
                    try:
                        chunks = document_processor.process_and_get_chunks(file_path)
                        parsed_text = "\n".join([chunk.page_content for chunk in chunks])

                        if len(parsed_text) > settings.gemini_max_input_token:
                            logger.warning(f"⚠️ {file_name} is massive. Saving to RAM for local BM25 search.")
                            ephemeral_chunks.extend(chunks)
                            file_context += f"\n[SYSTEM NOTE: The uploaded file '{file_name}' was too large to read instantly. It is stored in temporary memory. You MUST route to 'rag_only' or 'all' to augment it.]\n"
                        else:    
                            logger.debug(f"📄 {file_name} parsed successfully. Injecting directly.")
                            file_context += f"--- Start of Content: {file_name} (Type: {file_type}) ---\n{parsed_text}\n--- End of {file_name} ---\n\n"

                    except Exception as e:
                        logger.exception(f"Failed to parse uploaded file {file_name}")
                        file_context += f"--- Start of Content: {file_name} ---\n[Error: Could not extract text from this file.]\n--- End of {file_name} ---\n\n"
                
                # CASE 3: Heavy Genomic File (S3 URI)
                elif rustfs_uri:
                    logger.debug(f"Skipping local parsing for {file_name}. It is a backend dataset.")
                    file_context += f"\n[SYSTEM NOTE: The user uploaded a backend dataset '{file_name}'. S3 URI: {rustfs_uri}. Description: {description}. Pass this URI to the relevant bioinformatics tools.]\n"
                
                # Failsafe
                else:
                    logger.warning(f"File {file_name} missing required fields (local_content, file_path, or rustfs_uri).")
            if file_context:
                file_context = f"The user has uploaded the following files for context. Use this information to answer their query:\n\n{file_context}"
                logger.debug("Successfully extracted file content and constructed SystemMessage.")
        else:
            logger.debug("No uploaded files provided")

        msg = SystemMessage(content=file_context) if file_context else None

        if msg:
            logger.debug("Injecting SystemMessage into state.messages")
        else:
            logger.debug("No SystemMessage injected")

        current_iter = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations")

        logger.debug(f"Iteration count: {current_iter}")
        logger.debug(f"Max iterations: {max_iter}")

        elapsed = int((time.time() - start_time) * 1000)
        logger.debug(f"Input Analyzer execution time: {elapsed} ms")

        return Command(
            goto=AgentGraphNode.ROUTER,
            update={
                "messages": [msg] if msg else [],
                "uploaded_chunks": ephemeral_chunks,
                "tool_results": [],
                "web_results": [],
                "rag_results": [],
                "iteration_count": 0,
                "required_tools": []
            }
        )

    return input_analyzer