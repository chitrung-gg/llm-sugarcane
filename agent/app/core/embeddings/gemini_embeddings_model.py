import os
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field, PrivateAttr

from app.configs.settings.settings import get_settings


class GeminiEmbeddingModel(BaseModel):
    model_name: str = Field(
        default_factory=lambda: get_settings().gemini_embedding_model
    )

    _embeddings: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        # This method will run immediately after class initiated

        self._embeddings = GoogleGenerativeAIEmbeddings(model=self.model_name)

    def get_embeddings(self):
        return self._embeddings