from typing import List
from loguru import logger
from flashrank import Ranker
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from langchain_core.documents import Document
from app.configs.settings.settings import get_settings

class RerankerService:
    def __init__(self):
        self._reranker_instance = None
        self.settings = get_settings()

    def _get_reranker(self, top_n: int) -> FlashrankRerank:
        """Returns a singleton instance of the FlashRank compressor."""
        if self._reranker_instance is None:
            logger.info("Initializing FlashRank model... (This only happens once)")
            try:
                flashrank_client = Ranker(
                    model_name="ms-marco-MultiBERT-L-12"
                ) 

                self._reranker_instance = FlashrankRerank(
                    client=flashrank_client,
                    top_n=top_n
                )

                logger.info("FlashRank successfully loaded into memory.")
            except Exception as e:
                logger.error(f"Failed to load FlashRank: {e}")
                raise
                
        return self._reranker_instance

    def rerank_documents(
        self, 
        query: str, 
        documents: List[Document], 
        threshold: float, 
        top_k: int
    ) -> List[Document]:
        """
        Compresses documents using FlashRank, filters by threshold, 
        and enforces the exact top_k limit.
        """
        if not documents:
            return []
        if not top_k:
            top_k = self.settings.QDRANT_FINAL_TOP_K

        reranker = self._get_reranker(top_k)
        
        compressed_docs = reranker.compress_documents(
            documents=documents,
            query=query
        )

        filtered_docs = []
        for doc in compressed_docs:
            score = doc.metadata.get("relevance_score", 0.0)
            
            # if score < threshold:
            #     logger.debug(f"[Reranker] Chunk (Score: {score:.5f} < {threshold})")
            #     continue
                
            filtered_docs.append(doc)

        # 3. Return the exact number of top results requested
        return filtered_docs[:top_k]