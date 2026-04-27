import asyncio
import time
from typing import List, Literal, TypeAlias, cast
from langfuse import observe
from loguru import logger
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.common.constants import ObservationType
from app.utils.observability.tracing import tracing
from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.configs.settings.settings import get_settings
from app.core.graph.state.agent_state import AgentState, RAGResult
from app.core.prompts.rag_prompts import RAG_QUERY_OPTIMIZATION_PROMPT


import time
from loguru import logger
from langchain_qdrant import QdrantVectorStore

from app.core.graph.state.agent_state import AgentState, RAGResult

class OptimizedRagQuery(BaseModel):
    """Schema to force the LLM to output a clean semantic search string."""
    search_query: str = Field(
        description="A concise, standalone query optimized for semantic search. Maximum 15 words. DO NOT repeat words."
    )

def make_rag_node(
    vector_store_solid: QdrantVectorStore,
    vector_store_volatile: QdrantVectorStore,
    llm_service: LLMService
):
    @tracing(observation_type=ObservationType.RETRIEVER)
    async def rag(state: AgentState) -> Command[
        Literal[AgentGraphNode.SYNTHESIZER]
    ]:
        settings = get_settings()

        logger.debug("[RAG] 🔎 Starting vector search")
        start_time = time.time()
        
        original_query = state["query"]

        solid_k = getattr(settings, 'qdrant_solid_top_k', 5)
        volatile_k = getattr(settings, 'qdrant_volatile_top_k', 3)
        final_top_k = getattr(settings, 'rag_final_top_k', 5)
        max_query_length = getattr(settings, 'rag_max_query_length', 200)
                                   
        # 1. Query Optimization
        system_prompt = RAG_QUERY_OPTIMIZATION_PROMPT.format(
            conversation_summary=state.get("summary", "No prior context.")
        )

        messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
        if state["messages"]:
            messages.extend(state["messages"])        
        messages.append(HumanMessage(content=f"Latest Query: {original_query}"))

        try:
            rewriter_llm = llm_service.get_structured_quaternary_model(OptimizedRagQuery)
            rewritten_result: OptimizedRagQuery = await rewriter_llm.ainvoke(messages)
            optimized_query = rewritten_result.search_query

            # Circuit breaker to prevent runaway repetition
            if len(optimized_query) > max_query_length:
                logger.warning(f"[RAG] ⚠️ LLM hallucinated a repeating query. Triggering fallback.")
                optimized_query = original_query
            else:
                logger.info(f"[RAG] 🪄 Optimized query: '{optimized_query}' (Original: '{original_query}')")
        except Exception as e:
            logger.warning(f"[RAG] Query optimization failed: {e}. Falling back to original query.")
            optimized_query = original_query

        # 2. Dense Vector Search
        logger.debug(f"Executing Qdrant search with query: {optimized_query}")

        combined_results = []
        project_name = state.get("active_project_name")

        # Fetch from both stores
        solid_results = await vector_store_solid.asimilarity_search_with_score(optimized_query, k=solid_k)
        for doc, score in solid_results:
            doc.page_content = f"[SOURCE TIER: CURATED (High Trust)] {doc.page_content}"
            doc.metadata["source_tier"] = "CURATED"

        volatile_filter = None
        if project_name:
            # Assumes your ingestion service now tags chunks with 'project_name'
            volatile_filter = {"project_name": project_name}
        
        volatile_results = await vector_store_volatile.asimilarity_search_with_score(
            optimized_query, 
            k=volatile_k,
            filter=volatile_filter
        )

        for doc, score in volatile_results:
            doc.page_content = f"[SOURCE TIER: INFERRED/PROVISIONAL (Agent Discovery)] {doc.page_content}"
            doc.metadata["source_tier"] = "INFERRED"

        # Combine, sort by hybrid score descending, and take the absolute Top 5 overall
        combined_results = solid_results + volatile_results
        combined_results.sort(key=lambda x: x[1], reverse=True)
        top_semantic_results = combined_results[:final_top_k]

        logger.debug("Retrieved {count} total semantic documents", count=len(combined_results))

        new_rag_results = []
        new_sources = []

        # Process the combined results
        for idx, (doc, score) in enumerate(top_semantic_results):
            source_name = doc.metadata.get("source", "unknown")
            source_tier = doc.metadata.get("source_tier", "unknown_tier")

            logger.debug(
                "[RAG] Doc {idx} | tier={tier} | source={source_name} | score={score}",
                idx=idx, tier=source_tier, source_name=source_name, score=score
            )

            # Package into custom schema
            rag_item = RAGResult(
                content=doc.page_content,
                source_file=source_name,
                page_number=doc.metadata.get("page"),
                relevance_score=score,
            )
            new_rag_results.append(rag_item)

            source_item = {
                "document_id": doc.metadata.get("_id", f"doc_{idx}"),
                "source_file": source_name,
                "chunk_index": idx,
                "score": score,
                "source_tier": source_tier
            }
            new_sources.append(source_item)

        # 3. Sparse Keyword Search (BM25 - Uploaded files)
        ephemeral_chunks = state.get("uploaded_chunks", [])

        if ephemeral_chunks:
            logger.debug("[RAG] 🧬 Running BM25 Keyword Search on {count} uploaded chunks...", count=len(ephemeral_chunks))

            # Build BM25 matrix in a background thread to prevent async loop blocking
            def _build_bm25():
                return BM25Retriever.from_documents(
                    ephemeral_chunks,
                    k=getattr(settings, 'inmemory_retriever_top_k', 3),
                    bm25_variant="plus",
                )
            
            bm25_retriever = await asyncio.to_thread(_build_bm25)

            local_results = await bm25_retriever.ainvoke(optimized_query)

            for idx, doc in enumerate(local_results):
                # Dynamic Pseudo-Scoring: 1.0 for the best match, decaying by 0.05 for each subsequent match.
                # This guarantees ordinal ranking without a hardcoded threshold.
                dynamic_score = round(max(0.5, 1.0 - (idx * 0.05)), 2)

                rag_item = RAGResult(
                    content=doc.page_content,
                    source_file=doc.metadata.get("source", "uploaded_file"),
                    page_number=doc.metadata.get("alignment_info", None),
                    relevance_score=dynamic_score, 
                )
                new_rag_results.append(rag_item)
                
                new_sources.append({
                    "document_id": f"ephemeral_chunk_{idx}",
                    "source_file": doc.metadata.get("source", "uploaded_file"),
                    "score": dynamic_score,
                    "chunk_index": idx
                })
                
            logger.debug(f"[RAG] ✅ Found {len(local_results)} matches in uploaded files.")
        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            "[RAG] ✅ Search completed in {elapsed} ms | valid chunks kept={count}",
            elapsed=elapsed, count=len(new_rag_results)
        )

        # Because rag_results uses operator.add, returning a list appends it to state
        updates = {
            "rag_results": new_rag_results,
            "sources_used": new_sources,
        }

        # Cast to use the AgentState already defined
        # preview_state = cast(AgentState, {**state, **updates})
        
        # Get the destination using your separated logic class!
        # Dont need this as `synthesizer` node can execute parallel `web_search`
        # If not enough information, then it will call again
        # destination = check_rag_fallback(preview_state)

        # Return to Router node as following the ReAct pattern (Reasoning Loop)
        return Command(
            goto=AgentGraphNode.SYNTHESIZER,
            update=updates
        )

    return rag