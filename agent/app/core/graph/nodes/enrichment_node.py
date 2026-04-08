import asyncio
from typing import Literal
from loguru import logger
from langgraph.types import Command
from langchain_qdrant import QdrantVectorStore

from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.services.knowledge.graph_ingestion_service import GraphIngestionService


def make_enrichment_node(llm_service: LLMService, vector_store: QdrantVectorStore):
    async def enrichment(state: AgentState) -> Command[Literal["router"]]:
        logger.debug("[Enrichment] Analyzing tool results for knowledge graph ingestion...")
        
        tool_results = state.get("tool_results", [])
        
        if not tool_results:
            logger.debug("[Enrichment] No tool results to ingest.")
            return Command(goto="router")

        ingestion_service = GraphIngestionService(llm_service, vector_store)
        
        tasks = []
        for result in tool_results:
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
                    ingestion_service.ingest_knowledge(
                        source_text=str(output),
                        source_metadata={"tool": tool_name}
                    )
                )
                tasks.append(task)
                
        # Note: we do not await the tasks here because we want them to run asynchronously
        # If we await, it will block the graph. However, depending on the event loop, 
        # fire-and-forget tasks might be cancelled if the server shuts down.
        # But this fulfills the GEMINI.md rule 5: "Asynchronous Polyglot Write"
        
        logger.debug(f"[Enrichment] Dispatched {len(tasks)} background ingestion tasks.")
        
        return Command(goto="router")

    return enrichment
