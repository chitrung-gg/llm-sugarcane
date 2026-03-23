from functools import lru_cache
from typing import Any, Dict, List
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, PrivateAttr

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.configs.settings.settings import get_settings

class LLMService(BaseModel):
    """
    A streamlined LLM service focused on a single, robust primary model.
    No over-engineering, just clean configuration for LangGraph.
    """
    
    _primary_model: Any = PrivateAttr()
    _secondary_model: Any = PrivateAttr()
    
    def model_post_init(self, _context: Any):
        settings = get_settings()
        api_key = settings.google_api_key.get_secret_value() if settings.google_api_key else None

        if not api_key:
            raise ValueError("Google API Key not found!")

        self._primary_model = ChatGoogleGenerativeAI(
            model=settings.gemini_primary_model,
            google_api_key=api_key,
            temperature=0.0,        # Prioritize correctness
            max_retries=settings.llm_max_retries, 
        )

        self._secondary_model = ChatGoogleGenerativeAI(
            model=settings.gemini_secondary_model,
            google_api_key=api_key,
            temperature=0.0,        # Prioritize correctness
            max_retries=settings.llm_max_retries, 
        )
        
        logger.info(f"LLMService ready | Primary: {settings.gemini_primary_model} | Secondary: {settings.gemini_secondary_model}")

    def get_primary_model(self) -> BaseChatModel:
        return self._primary_model
    
    def get_secondary_model(self) -> BaseChatModel:
        return self._secondary_model

    
    
    