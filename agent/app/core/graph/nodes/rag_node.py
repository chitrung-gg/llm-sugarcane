import time
from loguru import logger
from langchain_qdrant import QdrantVectorStore

from app.core.graph.state.agent_state import AgentState


def make_rag_node(vector_store: QdrantVectorStore):

    async def rag(state: AgentState) -> dict:
        logger.debug("[RAG] 🔎 Starting vector search")

        start_time = time.time()

        query = state["query"]
        logger.debug(f"[RAG] Query: {query}")

        # Perform similarity search
        docs = await vector_store.asimilarity_search(query, k=3)

        logger.debug(f"[RAG] Retrieved {len(docs)} raw documents")

        new_rag_results = []
        new_sources = []

        for idx, doc in enumerate(docs):
            source_name = doc.metadata.get("source", "unknown")
            score = doc.metadata.get("score")

            logger.debug(
                f"[RAG] Doc {idx} | "
                f"source={source_name} | "
                f"score={score}"
            )

            rag_item = {
                "content": doc.page_content,
                "source_file": source_name,
                "page_number": doc.metadata.get("page"),
                "relevance_score": score,
            }
            new_rag_results.append(rag_item)

            source_item = {
                "document_id": doc.metadata.get("_id", f"doc_{idx}"),
                "source_file": source_name,
                "chunk_index": idx,
                "score": score,
            }
            new_sources.append(source_item)

        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[RAG] ✅ Search completed in {elapsed} ms | "
            f"chunks={len(new_rag_results)}"
        )

        return {
            "rag_results": new_rag_results,
            "sources_used": new_sources,
        }

    return rag