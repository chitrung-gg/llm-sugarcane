import asyncio
from typing import Literal
from loguru import logger
from langgraph.types import Command

from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.knowledge.graph_ingestion_service import GraphIngestionService

def make_enrichment_node(
    graph_ingestion_service: GraphIngestionService
):
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
            # We only want to enrich data from external sources (e.g., NCBI APIs)
            # Add logic here to filter which tools should trigger ingestion.
            # Assuming any tool that brings back large text output or JSON should be parsed.
            
            tool_name = result.get("tool_name", "") if isinstance(result, dict) else getattr(result, "tool_name", "")
            status = result.get("status", "") if isinstance(result, dict) else getattr(result, "status", "")
            output = result.get("output", "") if isinstance(result, dict) else getattr(result, "output", "")
            
            if status == "success" and len(str(output)) > 50:
                logger.info(f"[Enrichment] Triggering async ingestion for tool: {tool_name}")
                
                # We use asyncio.create_task to run it in the background without blocking the LangGraph workflow
                # In a production environment, this should ideally be a Celery task.
                # For now, we fire and forget in the current event loop.
                task = asyncio.create_task(
                    graph_ingestion_service.ingest_knowledge(
                        source_text=str(output),
                        source_metadata={"tool": tool_name}
                    )
                )
                
        # Note: we do not await the tasks here because we want them to run asynchronously
        # If we await, it will block the graph. However, depending on the event loop, 
        # fire-and-forget tasks might be cancelled if the server shuts down.
        logger.debug(f"[Enrichment] Dispatched background ingestion tasks.")
        
        return Command(
            goto=AgentGraphNode.SYNTHESIZER
        )

    return enrichment
