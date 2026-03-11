import time
from loguru import logger
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever

from app.configs.settings.settings import get_settings
from app.core.graph.state.agent_state import AgentState, RAGResult


import time
from loguru import logger
from langchain_qdrant import QdrantVectorStore

from app.core.graph.state.agent_state import AgentState, RAGResult

def make_rag_node(vector_store: QdrantVectorStore):

    async def rag(state: AgentState) -> dict:
        settings = get_settings()

        logger.debug("[RAG] 🔎 Starting vector search")

        start_time = time.time()
        query = state["query"]
        logger.debug(f"[RAG] Query: {query}")

        # 1. USE WITH_SCORE to get the actual similarity metric
        raw_results = await vector_store.asimilarity_search_with_score(query, k=3)

        logger.debug(f"[RAG] Retrieved {len(raw_results)} raw documents")

        new_rag_results = []
        new_sources = []
        

        for idx, (doc, score) in enumerate(raw_results):
            source_name = doc.metadata.get("source", "unknown")

            logger.debug(
                f"[RAG] Doc {idx} | "
                f"source={source_name} | "
                f"score={score}"
            )

            # 3. FILTER OUT IRRELEVANT DOCS
            if score < settings.rag_score_threshold:
                logger.warning(f"[RAG] 🚫 Dropping Doc {idx} - Score {score} is below threshold {settings.rag_score_threshold}")
                continue

            # Package into custom schema
            rag_item = RAGResult(
                content=doc.page_content,
                source_file=source_name,
                page_number=doc.metadata.get("page"),
                relevance_score=score, # Now we have the real score!
            )
            new_rag_results.append(rag_item)

            source_item = {
                "document_id": doc.metadata.get("_id", f"doc_{idx}"),
                "source_file": source_name,
                "chunk_index": idx,
                "score": score,
            }
            new_sources.append(source_item)

        ephemeral_chunks = state.get("uploaded_chunks", [])

        if ephemeral_chunks:
            logger.debug(f"[RAG] 🧬 Running BM25 Keyword Search on {len(ephemeral_chunks)} uploaded chunks...")

            # Using BM25 plus variant
            bm25_retriever = BM25Retriever.from_documents(
                ephemeral_chunks,
                k=settings.retriever_top_k,
                bm25_variant="plus",
            )

            local_results = bm25_retriever.invoke(query)

            for idx, doc in enumerate(local_results):
                # We give local file matches a high synthetic score (0.90) 
                # because if it matched the keyword in the user's file, it is highly relevant.
                rag_item = RAGResult(
                    content=doc.page_content,
                    source_file=doc.metadata.get("source", "uploaded_file"),
                    page_number=doc.metadata.get("alignment_info", None),
                    relevance_score=0.90, 
                )
                new_rag_results.append(rag_item)
                
                new_sources.append({
                    "document_id": f"ephemeral_chunk_{idx}",
                    "source_file": doc.metadata.get("source", "uploaded_file"),
                    "score": 0.90,
                    "chunk_index": idx
                })
                
            logger.debug(f"[RAG] ✅ Found {len(local_results)} matches in uploaded files.")
        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[RAG] ✅ Search completed in {elapsed} ms | "
            f"valid chunks kept={len(new_rag_results)}"
        )

        # Because rag_results uses operator.add, returning a list appends it to state
        return {
            "rag_results": new_rag_results,
            "sources_used": new_sources,
        }

    return rag