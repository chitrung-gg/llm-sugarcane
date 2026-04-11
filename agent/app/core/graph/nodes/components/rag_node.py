import time
from typing import List, Literal, TypeAlias, cast
from loguru import logger
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.routing.check_rag_fallback import check_rag_fallback
from app.configs.settings.settings import get_settings
from app.core.graph.state.agent_state import AgentState, RAGResult


import time
from loguru import logger
from langchain_qdrant import QdrantVectorStore

from app.core.graph.state.agent_state import AgentState, RAGResult

RELEVANCE_SCORE = 0.90

class OptimizedRagQuery(BaseModel):
    """Schema to force the LLM to output a clean semantic search string."""
    search_query: str = Field(
        description="A standalone, highly descriptive query optimized for semantic vector similarity search. Use rich biological keywords."
    )

def make_rag_node(
    vector_store: QdrantVectorStore,
    llm_service: LLMService
):
    async def rag(state: AgentState) -> Command[
        Literal[AgentGraphNode.SYNTHESIZER]
    ]:
        settings = get_settings()

        logger.debug("[RAG] 🔎 Starting vector search")
        start_time = time.time()
        
        original_query = state["query"]

        # 1. Query Optimization (Semantic Focus)
        system_prompt = f"""
            You are a Semantic Search Optimizer for a Sugarcane Genomics vector database.
            The user is asking a conversational question. Convert this into a standalone, highly descriptive query.
            
            CONVERSATION SUMMARY:
            {state.get("summary", "No prior context.")}
            
            RULES:
            - Vector databases match meaning, not just exact words. Provide rich, descriptive biological keywords.
            - Resolve pronouns ("it", "this cultivar") using the conversation summary.
            - Remove conversational filler ("Tell me about", "What is").
            - Output ONLY the optimized search string.
        """

        messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
        if state["messages"]:
            messages.extend(state["messages"])        
        messages.append(HumanMessage(content=f"Latest Query: {original_query}"))

        try:
            rewriter_llm = llm_service.get_quaternary_model().with_structured_output(OptimizedRagQuery)
            rewritten_result = await rewriter_llm.ainvoke(messages)
            optimized_query = OptimizedRagQuery.model_validate(rewritten_result).search_query
            logger.info(f"[RAG] 🪄 Optimized query: '{optimized_query}' (Original: '{original_query}')")
        except Exception as e:
            logger.warning(f"[RAG] Query optimization failed: {e}. Falling back to original query.")
            optimized_query = original_query

        # 2. Dense Vector Search
        logger.debug(f"Executing Qdrant search with query: {optimized_query}")

        raw_results = await vector_store.asimilarity_search_with_score(optimized_query, k=3)

        logger.debug("Retrieved {count} raw documents", count=len(raw_results))

        new_rag_results = []
        new_sources = []

        for idx, (doc, score) in enumerate(raw_results):
            source_name = doc.metadata.get("source", "unknown")

            logger.debug(
                "[RAG] Doc {idx} | source={source_name} | score={score}",
                idx=idx, source_name=source_name, score=score
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
            }
            new_sources.append(source_item)

        # 3. Sparse Keyword Search (BM25 - Uploaded files)
        ephemeral_chunks = state.get("uploaded_chunks", [])

        if ephemeral_chunks:
            logger.debug("[RAG] 🧬 Running BM25 Keyword Search on {count} uploaded chunks...", count=len(ephemeral_chunks))

            # Using BM25 plus variant
            bm25_retriever = BM25Retriever.from_documents(
                ephemeral_chunks,
                k=settings.inmemory_retriever_top_k,
                bm25_variant="plus",
            )

            local_results = bm25_retriever.invoke(optimized_query)

            for idx, doc in enumerate(local_results):
                # We give local file matches a high synthetic score (0.90) 
                # because if it matched the keyword in the user's file, it is highly that user want to read from his/her uploaded files
                rag_item = RAGResult(
                    content=doc.page_content,
                    source_file=doc.metadata.get("source", "uploaded_file"),
                    page_number=doc.metadata.get("alignment_info", None),
                    relevance_score=RELEVANCE_SCORE, 
                )
                new_rag_results.append(rag_item)
                
                new_sources.append({
                    "document_id": f"ephemeral_chunk_{idx}",
                    "source_file": doc.metadata.get("source", "uploaded_file"),
                    "score": RELEVANCE_SCORE,
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
        preview_state = cast(AgentState, {**state, **updates})
        
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