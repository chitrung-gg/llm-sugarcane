import time
import re
from typing import List, Literal, TypeAlias, cast
from langfuse import observe
from loguru import logger
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.core.vector_store.vector_store import build_metadata_filter
from app.common.constants import ObservationType
from app.utils.observability.tracing import tracing
from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.configs.settings.settings import get_settings
from app.core.graph.state.agent_state import AgentState, RAGResult
from app.core.prompts.rag_prompts import RAG_QUERY_OPTIMIZATION_PROMPT
from app.schemas.agent.rag import OptimizedRagQuery
from app.utils.graph.context_utils import get_recent_messages

def make_rag_node(
    vector_store_solid: QdrantVectorStore,
    vector_store_volatile: QdrantVectorStore,
    llm_service: LLMService
):
    @tracing(observation_type=ObservationType.RETRIEVER)
    async def rag(state: AgentState) -> Command[
        Literal[AgentGraphNode.INNER_SYNTHESIZER]
    ]:
        settings = get_settings()

        logger.debug("[RAG] 🔎 Starting vector search")
        start_time = time.time()
        
        original_query = state["query"]
        optimized_query = state.get("rag_query")

        solid_k = settings.QDRANT_SOLID_TOP_K
        volatile_k = settings.QDRANT_VOLATILE_TOP_K
        final_top_k = settings.QDRANT_FINAL_TOP_K
        max_query_length = settings.QDRANT_MAX_QUERY_LENGTH
                                   
        # 1. Query Optimization (Skip if Router already provided one)
        if not optimized_query:
            logger.info("[RAG] No pre-optimized query found. Rewriting...")
            system_prompt = RAG_QUERY_OPTIMIZATION_PROMPT.format(
                conversation_summary=state.get("summary", "No prior context."),
                user_question=original_query
            )

            # Include recent messages for better query rewriting
            recent_messages = get_recent_messages(state.get("messages", []), last_k_turns=3)

            messages: List[BaseMessage] = [
                SystemMessage(content=system_prompt),
                *recent_messages,
                HumanMessage(content=f"Latest Query: {original_query}")
            ]

            try:
                rewriter_llm = llm_service.get_structured_quaternary_model(OptimizedRagQuery)
                rewritten_result: OptimizedRagQuery = await rewriter_llm.ainvoke(messages)
                optimized_query = rewritten_result.search_query

                if len(optimized_query) > max_query_length:
                    logger.warning(f"[RAG] ⚠️ LLM hallucinated a repeating query. Triggering fallback.")
                    optimized_query = original_query
                else:
                    logger.debug(f"[RAG] 🪄 Optimized query: '{optimized_query}' (Original: '{original_query}')")
            except Exception as e:
                logger.warning(f"[RAG] Query optimization failed: {e}. Falling back to original query.")
                optimized_query = original_query
        else:
            logger.info(f"[RAG] Using pre-optimized query from Router: '{optimized_query}'")

        # 2. Extract active context
        active_datasets = state.get("active_datasets") or []
        dataset_ids = [ds.get("dataset_id") for ds in active_datasets if ds.get("dataset_id")]

        # 3. Qdrant Hybrid Search
        logger.debug(f"Executing Qdrant search with query: {optimized_query}")
        
        solid_results = await vector_store_solid.asimilarity_search_with_score(query=optimized_query, k=solid_k)
        for doc, score in solid_results:
            doc.page_content = f"[SOURCE TIER: CURATED (High Trust)] {doc.page_content}"
            doc.metadata["source_tier"] = "CURATED"

        volatile_results = []
        if dataset_ids:
            volatile_filter = build_metadata_filter({"dataset_id": dataset_ids})
            volatile_results = await vector_store_volatile.asimilarity_search_with_score(
                query=optimized_query, 
                k=volatile_k,
                filter=volatile_filter
            )

            for doc, score in volatile_results:
                doc.page_content = f"[SOURCE TIER: INFERRED/PROVISIONAL (Agent Discovery)] {doc.page_content}"
                doc.metadata["source_tier"] = "INFERRED"

        combined_results = solid_results + volatile_results
        combined_results.sort(key=lambda x: x[1], reverse=True)
        top_semantic_results = combined_results[:final_top_k]

        new_rag_results = []
        new_sources = []

        for idx, (doc, score) in enumerate(top_semantic_results):
            raw_filename = doc.metadata.get("original_filename") or doc.metadata.get("source_filename") or doc.metadata.get("source", "unknown")
            source_name = re.sub(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_', '', str(raw_filename))
            source_tier = doc.metadata.get("source_tier", "unknown_tier")

            rag_item = RAGResult(
                content=doc.page_content,
                source_file=source_name,
                page_number=doc.metadata.get("page"),
                relevance_score=score,
            )
            new_rag_results.append(rag_item)

            new_sources.append({
                "document_id": doc.metadata.get("_id", f"doc_{idx}"),
                "source_file": source_name,
                "chunk_index": idx,
                "score": score,
                "source_tier": source_tier
            })

        elapsed = int((time.time() - start_time) * 1000)

        return Command(
            goto=AgentGraphNode.INNER_SYNTHESIZER,
            update={
                "rag_results": new_rag_results,
                "sources_used": new_sources,
            }
        )

    return rag