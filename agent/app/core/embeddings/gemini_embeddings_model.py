import os
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, PrivateAttr


class GeminiEmbeddingModel(BaseModel):
    model_name: str = "gemini-embedding-001"

    _embeddings: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        # This method will run immediately after class initiated
        self._embeddings = GoogleGenerativeAIEmbeddings(model=self.model_name)

    def get_embeddings(self):
        return self._embeddings