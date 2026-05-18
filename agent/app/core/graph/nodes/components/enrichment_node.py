from typing import Dict, Literal, List
from loguru import logger
from langgraph.types import Command

from app.common.constants import ObservationType
from app.utils.observability.tracing import tracing
from app.core.tools.registry.ingestion_config_tool import IngestionConfig
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState

def make_enrichment_node(
    tool_registry: Dict[str, IngestionConfig]
):
    @tracing(observation_type=ObservationType.CHAIN)
    async def enrichment(state: AgentState) -> dict:
        logger.debug("[Enrichment] Analyzing tool results for knowledge graph ingestion...")

        tool_results = state.get("tool_results", [])
        required_tools = state.get("required_tools", [])
        
        if not tool_results:
            logger.debug("[Enrichment] No tool results to ingest.")
            return {
                
            }

        # Only process the results for tools just executed in this turn
        num_new = len(required_tools)
        new_results = tool_results[-num_new:] if num_new > 0 else []

        batch_payloads = []

        active_project = state.get("active_project") or {}
        project_name = active_project.get("project_name", "Default Workspace")
        project_id = active_project.get("project_id", "unknown")
        
        for result in new_results:
            tool_name = result.get("tool_name", "")
            status = result.get("status", "")
            output = str(result.get("output", ""))

            # Check if the tool_name exists as a key in our tool_registry
            if status == "success" and tool_name in tool_registry:
                logger.info(f"[Enrichment] Queueing ingestion for: {tool_name}")
                
                batch_payloads.append({
                    "source_text": output,
                    "source_metadata": {
                        "tool": tool_name,
                        "project_id": project_id
                    }
                })

        # try:
        #     # We use asyncio.to_thread to prevent the `requests` library from 
        #     # blocking the entire FastAPI/LangGraph event loop.
        #     await asyncio.to_thread(
        #         trigger_airflow_dag,
        #         conf_payload=batch_payloads,
        #         dag_id="knowledge_ingestion_pipeline"
        #     )
        # except Exception as e:
        #     logger.error(f"[Enrichment] Failed to trigger Airflow DAG via custom lib: {e}")

        if batch_payloads:
            logger.info(f"[Enrichment] Staging {len(batch_payloads)} items for deferred ingestion.")
            
            return {
                "extracted_knowledge": batch_payloads
            }
            

        return {

        }

    return enrichment
