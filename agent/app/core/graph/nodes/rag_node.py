import time
from loguru import logger
from langchain_qdrant import QdrantVectorStore

from app.core.graph.state.agent_state import AgentState, RAGResult


import time
from loguru import logger
from langchain_qdrant import QdrantVectorStore

from app.core.graph.state.agent_state import AgentState, RAGResult

def make_rag_node(vector_store: QdrantVectorStore):

    async def rag(state: AgentState) -> dict:
        logger.debug("[RAG] 🔎 Starting vector search")

        start_time = time.time()
        query = state["query"]
        logger.debug(f"[RAG] Query: {query}")

        # 1. USE WITH_SCORE to get the actual similarity metric
        raw_results = await vector_store.asimilarity_search_with_score(query, k=3)

        logger.debug(f"[RAG] Retrieved {len(raw_results)} raw documents")

        new_rag_results = []
        new_sources = []
        
        # 2. SET A THRESHOLD (You may need to tune this between 0.65 and 0.8)
        SCORE_THRESHOLD = 0.70 

        for idx, (doc, score) in enumerate(raw_results):
            source_name = doc.metadata.get("source", "unknown")

            logger.debug(
                f"[RAG] Doc {idx} | "
                f"source={source_name} | "
                f"score={score}"
            )

            # 3. FILTER OUT IRRELEVANT DOCS
            if score < SCORE_THRESHOLD:
                logger.warning(f"[RAG] 🚫 Dropping Doc {idx} - Score {score} is below threshold {SCORE_THRESHOLD}")
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