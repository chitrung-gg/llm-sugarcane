import asyncio
from typing import Dict, Literal
from loguru import logger
from langgraph.types import Command

from app.common.constants import ObservationType
from app.utils.observability.tracing import tracing
from app.core.tools.registry.ingestion_config_tool import IngestionConfig
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.ingestion.graph_ingestion_service import GraphIngestionService

_background_tasks = set()

def make_enrichment_node(
    graph_ingestion_service: GraphIngestionService,
    tool_registry: Dict[str, IngestionConfig]
):
    @tracing(observation_type=ObservationType.CHAIN)
    async def enrichment(state: AgentState) -> Command[
        Literal[AgentGraphNode.SYNTHESIZER]
    ]:
        logger.debug("[Enrichment] Analyzing tool results for knowledge graph ingestion...")
        tool_results = state.get("tool_results", [])
        required_tools = state.get("required_tools", []) # Add this line
        
        if not tool_results:
            logger.debug("[Enrichment] No tool results to ingest.")
            return Command(
                goto=AgentGraphNode.SYNTHESIZER
            )

        # Only process the results for tools just executed in this turn
        num_new = len(required_tools)
        new_results = tool_results[-num_new:] if num_new > 0 else []

        for result in new_results:
            if isinstance(result, dict):
                tool_name = result.get("tool_name", "")
                status = result.get("status", "")
                output = str(result.get("output", ""))
            else:
                tool_name = getattr(result, "tool_name", "")
                status = getattr(result, "status", "")
                output = str(getattr(result, "output", ""))
            
            # Check if the tool_name exists as a key in our tool_registry
            if status == "success" and len(str(output)) > 50 and tool_name in tool_registry:
                # Fetch the config just to log it nicely
                config = tool_registry[tool_name]
                logger.info(
                    f"[Enrichment] Triggering async ingestion for: {tool_name} "
                    f"(Target: {config.vector_store_type.value.upper()})"
                )
                
                # Create the task
                task = asyncio.create_task(
                    graph_ingestion_service.ingest_knowledge(
                        source_text=output,
                        source_metadata={"tool": tool_name}
                    )
                )
                
                # Protect it from Python's Garbage Collector
                _background_tasks.add(task)
                
                # Discard it from the set automatically when it finishes
                task.add_done_callback(_background_tasks.discard)
                
        # Note: we do not await the tasks here because we want them to run asynchronously
        # If we await, it will block the graph. However, depending on the event loop, 
        # fire-and-forget tasks might be cancelled if the server shuts down.
        logger.debug(f"[Enrichment] Dispatched background ingestion tasks.")
        
        return Command(
            goto=AgentGraphNode.SYNTHESIZER
        )

    return enrichment
