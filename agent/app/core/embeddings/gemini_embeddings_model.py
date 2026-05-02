import asyncio
import os
from typing import Any, List

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from loguru import logger
from pydantic import BaseModel, ConfigDict, PrivateAttr
from langchain_core.embeddings import Embeddings

from app.configs.settings.settings import get_settings


class GeminiEmbeddingModel(BaseModel, Embeddings):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _embeddings: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        settings = get_settings()
        embedding_google_api_key = settings.EMBEDDING_GOOGLE_API_KEY
        model_name = settings.GEMINI_EMBEDDING_MODEL

        if not embedding_google_api_key:
            raise ValueError("No Google API Keys found! Please set EMBEDDING_GOOGLE_API_KEY in .env.")

        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=model_name,
            api_key=embedding_google_api_key
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        logger.debug(f"Embedding {len(texts)} documents with Gemini...")
        try:
            # 1. Try the native LangChain batch embedding first (Faster)
            embeddings = self._embeddings.embed_documents(texts)
            
            # 2. If the API squashes the batch (the bug you are experiencing)
            if len(embeddings) != len(texts):
                logger.warning(
                    f"Mismatched length (Gemini): {len(texts)} input, {len(embeddings)} output. "
                    "Underlying API squashed the batch. Falling back to sequential embedding..."
                )
                # Fallback: Process them 1-by-1 to guarantee a 1:1 input/output mapping
                embeddings = [self._embeddings.embed_query(text) for text in texts]
                
            return embeddings
            
        except Exception as e:
            logger.error(f"Gemini embedding failed for batch of {len(texts)}: {e}")
            logger.error(f"Batch content: {texts}")
            raise e

    def embed_query(self, text: str) -> List[float]:
        return self._embeddings.embed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        logger.debug(f"Async embedding {len(texts)} documents with Gemini...")
        try:
            # 1. Try native async batch
            embeddings = await self._embeddings.aembed_documents(texts)
            
            # 2. Self-healing fallback if the API squashes the batch
            if len(embeddings) != len(texts):
                logger.warning(
                    f"Mismatched async length: {len(texts)} input, {len(embeddings)} output. "
                    "Falling back to concurrent async embedding..."
                )
                # Run them concurrently using asyncio.gather for blazing fast speed
                tasks = [self._embeddings.aembed_query(text) for text in texts]
                embeddings = await asyncio.gather(*tasks)
                
            return embeddings
            
        except Exception as e:
            logger.error(f"Async Gemini embedding failed for batch of {len(texts)}: {e}")
            raise e

    async def aembed_query(self, text: str) -> List[float]:
        return await self._embeddings.aembed_query(text)
    
    def get_embeddings(self) -> Embeddings:
        return self._embeddings