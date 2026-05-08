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
from app.utils.graph.context_utils import get_recent_messages, format_optimized_workspace

def make_input_analyzer_node(document_processor: DocumentProcessor, llm_service: LLMService):
    @tracing(observation_type=ObservationType.CHAIN)
    async def input_analyzer(state: AgentState) -> Command[
        Literal[AgentGraphNode.ROUTER]
    ]:
        start_time = time.time()
        logger.debug("========== [Input Analyzer Node] ==========")
        
        query = state.get("query", "")
        summary = state.get("summary", "")
        past_steps = state.get("past_steps", [])
        active_project = state.get("active_project")
        datasets = state.get("active_datasets") or []
        system_datasets = state.get("system_datasets", [])

        filtered_datasets = datasets
        
        if len(datasets) > 1:
            logger.info(f"[Input Analyzer] ✂️ Pruning {len(datasets)} active datasets for relevance...")
            
            # 1. Build an Enriched Context Query
            # Include recent messages and unified workspace context
            recent_messages_text = "\n".join([f"{m.type}: {m.content}" for m in get_recent_messages(state.get("messages", []), n=3)])
            
            step_history = "\n".join([f"- Step {obs.step_id}: {obs.summary}" for obs in past_steps]) if past_steps else "None"
            
            # Use the optimized utility for the file list
            workspace_context = format_optimized_workspace(active_project, datasets, system_datasets)
            
            enriched_query = (
                f"--- CONVERSATION HISTORY ---\n"
                f"{summary}\n"
                f"{recent_messages_text}\n\n"
                f"--- RESEARCH PROGRESS (PAST STEPS) ---\n"
                f"{step_history}\n\n"
                f"--- CURRENT TASK ---\n"
                f"{query}"
            )
            
            try:
                # Use Tier 3 (Flash Lite) for quick selection
                pruner = llm_service.get_structured_tertiary_model(PruningOutput)
                
                selection: PruningOutput = await pruner.ainvoke(
                    INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT.format(
                        query=enriched_query, 
                        file_list=workspace_context # Now uses the unified, clean XML structure
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
                "original_datasets": datasets,
                "system_datasets": system_datasets,
                "iteration_count": 0,
                "required_tools": []
            }
        )

    return input_analyzer
