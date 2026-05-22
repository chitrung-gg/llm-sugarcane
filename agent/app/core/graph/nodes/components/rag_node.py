import asyncio
import time
import re
import hashlib
from typing import List, Literal, cast
from langfuse import observe
from loguru import logger
from qdrant_client.http import models
from langchain_qdrant import QdrantVectorStore
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from langgraph.types import Command

from app.services.llm.reranker_service import RerankerService
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
    llm_service: LLMService,
    reranker_service: RerankerService 
):
    @tracing(observation_type=ObservationType.RETRIEVER)
    async def rag(state: AgentState) -> dict:
        settings = get_settings()

        logger.debug("[RAG] 🔎 Starting vector search with FlashRank Integration")
        start_time = time.time()
        
        original_query = state["query"]
        optimized_query = state.get("rag_query")

        # Use larger K for the broad fetch to give Reranker more options
        solid_k = settings.QDRANT_SOLID_TOP_K 
        volatile_k = settings.QDRANT_VOLATILE_TOP_K
        max_query_length = settings.QDRANT_MAX_QUERY_LENGTH

        if not optimized_query:
            logger.info("[RAG] No pre-optimized query found. Rewriting...")
            system_prompt = RAG_QUERY_OPTIMIZATION_PROMPT.format(
                conversation_summary=state.get("summary", "No prior context."),
                user_question=original_query
            )

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

        active_datasets = state.get("active_datasets") or []
        dataset_ids = [ds.get("dataset_id") for ds in active_datasets if ds.get("dataset_id")]

        logger.debug(f"Executing Qdrant search with query: {optimized_query}")
        
        # 2. Broad Qdrant Search
        solid_results = await vector_store_solid.asimilarity_search(
            query=optimized_query, 
            k=solid_k
        )

        # 3. Native Deduplication
        seen_payloads = set()
        solid_docs = []
        for doc in solid_results:
            # Hash the actual content to ensure we only drop 100% exact duplicates
            doc_hash = hashlib.md5(doc.page_content.strip().encode('utf-8')).hexdigest()
            
            if doc_hash not in seen_payloads:
                seen_payloads.add(doc_hash)
                doc.metadata["source_tier"] = doc.metadata.get("source_tier", "CURATED")
                solid_docs.append(doc)
            else:
                logger.debug("[RAG] 🗑️ Dropped exact duplicate Qdrant chunk.")

        volatile_docs = []
        if dataset_ids:
            # Combine filters
            volatile_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.dataset_id",
                        match=models.MatchAny(any=dataset_ids)
                    )
                ]
            )
 
            volatile_results = await vector_store_volatile.asimilarity_search(
                query=optimized_query, 
                k=volatile_k,
                filter=volatile_filter
            )
            
            for doc in volatile_results:
                doc_hash = hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()
                if doc_hash not in seen_payloads:
                    seen_payloads.add(doc_hash)
                    doc.metadata["source_tier"] = doc.metadata.get("source_tier", "INFERRED")
                    volatile_docs.append(doc)
                else:
                    logger.debug("[RAG] 🗑️ Dropped duplicate Qdrant chunk (VOLATILE).")

        # 3. Multi-Store Fusion & Reranking
        combined_docs = solid_docs + volatile_docs
        
        if not combined_docs:
            logger.warning("[RAG] No documents retrieved from databases.")
            final_docs = []
        else:
            logger.debug(f"[RAG] Reranking {len(combined_docs)} total chunks using FlashRank...")
            final_docs = await asyncio.to_thread(
                reranker_service.rerank_documents,
                query=original_query,
                documents=combined_docs,
                top_k=settings.QDRANT_FINAL_TOP_K
            )

        # 5. Output Formatting & Thresholding
        new_rag_results = []
        new_sources = []

        for idx, doc in enumerate(final_docs):
            raw_score = doc.metadata.get("relevance_score", 0.0)
            relevance_score = float(raw_score)      

            raw_filename = doc.metadata.get("original_filename") or doc.metadata.get("source_filename") or doc.metadata.get("source", "unknown")
            source_name = re.sub(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_', '', str(raw_filename))
            source_tier = doc.metadata.get("source_tier", "unknown_tier")

            rag_item = RAGResult(
                content=doc.page_content,
                source_file=source_name,
                page_number=doc.metadata.get("page"),
                relevance_score=relevance_score, 
            )
            new_rag_results.append(rag_item)

            new_sources.append({
                "document_id": doc.metadata.get("_id", f"doc_{idx}"),
                "file_id": doc.metadata.get("file_id"),         
                "entities": doc.metadata.get("entities", []),   
                "source_file": source_name,
                "chunk_index": idx,
                "score": relevance_score, 
                "source_tier": source_tier
            })

        elapsed = int((time.time() - start_time) * 1000)
        logger.info(f"[RAG] 🎯 Final top {len(new_rag_results)} chunks extracted in {elapsed}ms.")

        return {
            "rag_results": new_rag_results,
            "sources_used": new_sources,
        }

    return rag