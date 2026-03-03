from functools import lru_cache
from typing import Any, Dict, List
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ConfigDict, PrivateAttr

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.configs.settings.settings import get_settings

class LLMService(BaseModel):
    """
    A streamlined LLM service focused on a single, robust primary model.
    No over-engineering, just clean configuration for LangGraph.
    """

    def model_post_init(self, _context: Any):
        settings = get_settings()
        api_key = settings.google_api_key.get_secret_value() if settings.google_api_key else None

        if not api_key:
            raise ValueError("Google API Key not found!")

        self._primary_llm = ChatGoogleGenerativeAI(
            model=settings.gemini_llm_model,
            google_api_key=api_key,
            temperature=0.0,        # Prioritize correctness
            max_retries=settings.llm_max_retries, 
        )
        
        print(f"LLMService ready: {settings.gemini_llm_model}")

    def get_model(self) -> BaseChatModel:
        return self._primary_llm