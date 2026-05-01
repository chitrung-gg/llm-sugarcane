from functools import lru_cache
from typing import Any, Dict, List, Type
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, PrivateAttr

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from google.api_core import exceptions as google_exceptions

from app.configs.settings.settings import get_settings

class LLMService(BaseModel):
    """
    A streamlined LLM service focused on a single, robust primary model.
    Includes a robust retry strategy for transient errors using LangChain's native with_retry.
    """
    
    _primary_model: Any = PrivateAttr()
    _secondary_model: Any = PrivateAttr()
    _tertiary_model: Any = PrivateAttr()
    _quaternary_model: Any = PrivateAttr()

    _retry_config: Dict[str, Any] = PrivateAttr()
    
    def model_post_init(self, _context: Any):
        settings = get_settings()
        api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else None

        if not api_key:
            raise ValueError("Google API Key not found!")

        # Define transient errors to retry
        transient_errors = (
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
            google_exceptions.InternalServerError,
            google_exceptions.Aborted,
            google_exceptions.Unknown,
        )

        common_config = {
            "google_api_key": api_key,
            "temperature": 0.0,
            # "max_retries": settings.llm_max_retries,  # We'll use LangChain's with_retry instead of the basic provider retry
            "timeout": settings.LLM_TIMEOUT,  
        }
        
        self._retry_config = {
            "retry_if_exception_type": transient_errors,
            "wait_exponential_jitter": True, 
            "stop_after_attempt": settings.LLM_MAX_RETRIES, 
            "exponential_jitter_params": {
                "initial": 0.5,
                "max": 2.0,
                "jitter": 0.5
            }
        }

        self._primary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_PRIMARY_MODEL, 
            **common_config
        )
        self._secondary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_SECONDARY_MODEL,
            **common_config
        )
        self._tertiary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_TERTIARY_MODEL,
            **common_config
        )
        self._quaternary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_QUATERNARY_MODEL,
            **common_config
        )

        logger.info(f"""
            LLMService ready with Native Retry Strategy |
            Primary: {settings.GEMINI_PRIMARY_MODEL} |
            Secondary: {settings.GEMINI_SECONDARY_MODEL} |
            Tertiary: {settings.GEMINI_TERTIARY_MODEL} |
            Quaternary: {settings.GEMINI_QUATERNARY_MODEL}
            Max Attempts: {settings.LLM_MAX_RETRIES} | Timeout: {settings.LLM_TIMEOUT}s
        """)

    def get_primary_model(self) -> BaseChatModel:
        return self._primary_model
    
    def get_secondary_model(self) -> BaseChatModel:
        return self._secondary_model
    
    def get_tertiary_model(self) -> BaseChatModel:
        return self._tertiary_model
    
    def get_quaternary_model(self) -> BaseChatModel:
        return self._quaternary_model

    def get_structured_primary_model(self, schema: Type[BaseModel]) -> Runnable:
        """Returns a primary model configured with structured output AND retry logic."""
        return self._primary_model.with_structured_output(schema).with_retry(**self._retry_config)
    
    def get_structured_secondary_model(self, schema: Type[BaseModel]) -> Runnable:
        """Returns a primary model configured with structured output AND retry logic."""
        return self._secondary_model.with_structured_output(schema).with_retry(**self._retry_config)
    
    def get_structured_tertiary_model(self, schema: Type[BaseModel]) -> Runnable:
        """Returns a primary model configured with structured output AND retry logic."""
        return self._tertiary_model.with_structured_output(schema).with_retry(**self._retry_config)
    
    def get_structured_quaternary_model(self, schema: Type[BaseModel]) -> Runnable:
        """Returns a primary model configured with structured output AND retry logic."""
        return self._quaternary_model.with_structured_output(schema).with_retry(**self._retry_config)
    
    