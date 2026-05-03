import time
from loguru import logger
from typing import Any, Dict, List, Literal, Optional

from app.common.constants import ObservationType
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.utils.document_processor import DocumentProcessor
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.schemas.agent.pruning import PruningOutput
from app.core.prompts.input_analyzer_prompts import INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT
from langgraph.types import Command


# Wrap in factory method
def make_input_analyzer_node(document_processor: DocumentProcessor, llm_service: LLMService):
    @tracing(observation_type=ObservationType.CHAIN)
    async def input_analyzer(state: AgentState) -> Command[
        Literal[AgentGraphNode.ROUTER]
    ]:
        start_time = time.time()

        logger.debug("========== [Input Analyzer Node] ==========")
        
        query = state.get("query", "")
        project = state.get("active_project")
        datasets = state.get("active_datasets") or []

        # If we have multiple datasets/files, ask the fast model to filter them
        filtered_datasets = datasets
        
        if len(datasets) > 1:
            logger.info(f"[Input Analyzer] ✂️ Pruning {len(datasets)} active datasets for relevance...")
            
            # Format file list for the LLM
            file_list_str = ""
            for ds in datasets:
                ds_name = ds.get('dataset_name', 'Unknown')
                ds_id = ds.get('dataset_id', 'N/A')
                
                # Extract file names from both categories
                g_files = [f.get("file_name") for f in ds.get("genomic_files", [])]
                k_files = [f.get("file_name") for f in ds.get("knowledge_files", [])]
                
                file_list_str += f"- Dataset ID: {ds_id} | Name: '{ds_name}'\n"
                if g_files:
                    file_list_str += f"  * Genomic: {', '.join(g_files)}\n"
                if k_files:
                    file_list_str += f"  * Knowledge: {', '.join(k_files)}\n"

            try:
                # Use Tier 3 (Flash Lite) for quick selection
                pruner = llm_service.get_structured_tertiary_model(PruningOutput)
                
                selection: PruningOutput = await pruner.ainvoke(
                    INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT.format(
                        query=query,
                        file_list=file_list_str
                    )
                )

                logger.debug(f"[Input Analyzer] Scratchpad: {selection.scratchpad}")
                logger.info(f"[Input Analyzer] Result: {selection.reasoning}")

                # Map relevant IDs back to dataset objects
                relevant_ids = [str(rid) for rid in selection.relevant_file_ids]
                filtered_datasets = [
                    ds for ds in datasets 
                    if str(ds.get('dataset_id')) in relevant_ids
                ]
                
                logger.info(f"[Input Analyzer] Kept {len(filtered_datasets)}/{len(datasets)} datasets.")
                
            except Exception as e:
                logger.error(f"[Input Analyzer] ❌ Pruning failed: {e}. Falling back to full context.")
                filtered_datasets = datasets

        logger.debug(f"Input Analyzer execution time: {int((time.time() - start_time) * 1000)} ms")

        return Command(
            goto=AgentGraphNode.ROUTER,
            update={
                "active_datasets": filtered_datasets, 
                
                # Reset execution tracking arrays for this step
                "tool_results": [],
                "web_results": [],
                "rag_results": [],
                "iteration_count": 0,
                "required_tools": []
            }
        )

    return input_analyzer
