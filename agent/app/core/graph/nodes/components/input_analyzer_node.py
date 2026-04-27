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

        file_context = ""
        ephemeral_chunks = []

        project = state.get("active_project_name", "Default Project")
        datasets = state.get("active_datasets", [])

        # Hierarchical Workspace Context Injection
        workspace_header = f"### ACTIVE WORKSPACE CONTEXT\n- **Project**: {project}\n"
        if datasets:
            workspace_header += "- **Active Cultivars/Datasets**:\n"
            for ds in datasets:
                ds_name = ds.get('dataset_name', 'Unknown Cultivar')
                ds_id = ds.get('dataset_id', 'N/A')
                workspace_header += f"  - {ds_name} (ID: {ds_id})\n"
                
                # List files associated with this cultivar
                files = ds.get('files', [])
                if files:
                    workspace_header += "    Available Files:\n"
                    for f in files:
                        f_name = f.get('file_name')
                        f_type = f.get('file_type')
                        f_uri = f.get('rustfs_uri')
                        workspace_header += f"    * {f_name} (Type: {f_type}, URI: {f_uri})\n"
        
        file_context += workspace_header + "\n"

        # Note: 'uploaded_files' is now legacy/ephemeral. 
        # Most data now flows through 'active_datasets' (NotebookLM pattern).
        # legacy_files = state.get("uploaded_files", [])
        # if legacy_files:
        #     # ... process legacy files if needed ...
        #     pass

        current_iter = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations")

        logger.debug(f"Input Analyzer execution time: {int((time.time() - start_time) * 1000)} ms")

        return Command(
            goto=AgentGraphNode.ROUTER,
            update={
                "file_context": file_context,
                "uploaded_chunks": ephemeral_chunks,
                "tool_results": [],
                "web_results": [],
                "rag_results": [],
                "iteration_count": 0,
                "required_tools": []
            }
        )

    return input_analyzer
