import threading
from typing import List, Optional
from loguru import logger
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
import torch

# Prevent PyTorch's internal OpenMP/MKL thread pool from deadlocking when
# model.predict() is called inside asyncio.to_thread (a ThreadPoolExecutor thread).
torch.set_num_threads(1)

from app.configs.settings.settings import get_settings

class RerankerService:
    def __init__(self):
        self._model_instance = None
        self._lock = threading.Lock()
        self.settings = get_settings()

    def _get_model(self) -> CrossEncoder:
        """Returns a thread-safe singleton instance of the HuggingFace CrossEncoder."""
        if self._model_instance is None:
            with self._lock:
                if self._model_instance is None:
                    logger.info("Initializing HuggingFace Cross-Encoder model... (This only happens once)")
                    try:
                        model_name = "BAAI/bge-reranker-base"
                        self._model_instance = CrossEncoder(model_name)
                        logger.info(f"Cross-Encoder ({model_name}) successfully loaded into memory.")
                    except Exception as e:
                        logger.error(f"Failed to load Cross-Encoder: {e}")
                        raise
            
        return self._model_instance

    def rerank_documents(
        self, 
        query: str, 
        documents: List[Document], 
        absolute_floor: float = 0.6, 
        relative_tolerance: float = 0.85, 
        top_k: Optional[int] = None
    ) -> List[Document]:
        """
        Scores documents using a Cross-Encoder, normalizes via native PyTorch Sigmoid,
        and applies a Hybrid Threshold (Absolute Floor + Relative Drop-off).
        """
        if not documents:
            return []
            
        if top_k is None:
            top_k = self.settings.QDRANT_FINAL_TOP_K

        model = self._get_model()
        
        # 1. Prepare pairs
        text_pairs = [[query, doc.page_content] for doc in documents]
        
        # 2. Get raw logits (Linter is happy because we only pass the text)
        raw_scores = model.predict(text_pairs)

        # 3. Apply PyTorch's highly optimized native Sigmoid to the entire array at once!
        scores = torch.sigmoid(torch.tensor(raw_scores)).tolist()

        # 3. Attach scores to metadata
        processed_docs = []
        normalized_scores = []
        
        for doc, score in zip(documents, scores):
            # Convert NumPy float32 to standard Python float for JSON serialization downstream
            clean_score = float(score) 
            doc.metadata["relevance_score"] = clean_score
            processed_docs.append(doc)
            normalized_scores.append(clean_score)

        if not normalized_scores:
            return []
            
        best_score = max(normalized_scores)

        # 4. Check
        if best_score < absolute_floor:
            logger.warning(
                f"[Reranker] ALL documents failed the absolute floor "
                f"({best_score:.4f} < {absolute_floor}). Returning empty list."
            )
            return []
        
        dynamic_threshold = best_score * relative_tolerance 

        logger.debug(f"[Reranker] Best: {best_score:.4f} | Dynamic Cutoff: {dynamic_threshold:.4f} | Floor: {absolute_floor}")

        # 5. Filter and Sort
        filtered_docs = []
        for doc in processed_docs:
            score = doc.metadata["relevance_score"]
            if score >= dynamic_threshold and score >= absolute_floor:
                filtered_docs.append(doc)
            else:
                logger.debug(f"[Reranker] Dropped Chunk (Score {score:.4f} failed cutoff/floor)")

        filtered_docs.sort(key=lambda x: x.metadata["relevance_score"], reverse=True)
        
        return filtered_docs[:top_k]