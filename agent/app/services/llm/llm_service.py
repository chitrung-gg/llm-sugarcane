import itertools
from functools import lru_cache
from typing import Any, Dict, List, Type, Union
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
    A robust LLM service that supports multi-API key rotation.
    Rotates through a model of API keys for each request to maximize quota and avoid rate limits.
    """
    
    _primary_model: Any = PrivateAttr()
    _secondary_model: Any = PrivateAttr()
    _tertiary_model: Any = PrivateAttr()
    _quaternary_model: Any = PrivateAttr()

    _retry_config: Dict[str, Any] = PrivateAttr()
    
    def model_post_init(self, _context: Any):
        settings = get_settings()
        primary_google_api_key = settings.PRIMARY_GOOGLE_API_KEY.get_secret_value() if settings.PRIMARY_GOOGLE_API_KEY else None
        secondary_google_api_key = settings.SECONDARY_GOOGLE_API_KEY.get_secret_value() if settings.SECONDARY_GOOGLE_API_KEY else None
        tertiary_google_api_key = settings.TERTIARY_GOOGLE_API_KEY.get_secret_value() if settings.TERTIARY_GOOGLE_API_KEY else None
        quaternary_google_api_key = settings.QUATERNARY_GOOGLE_API_KEY.get_secret_value() if settings.QUATERNARY_GOOGLE_API_KEY else None

        if not primary_google_api_key:
            raise ValueError("No Google API Keys found! Please set GOOGLE_API_KEY in .env (comma-separated for multiple).")
        if not secondary_google_api_key:
            raise ValueError("No Google API Keys found! Please set GOOGLE_API_KEY in .env (comma-separated for multiple).")
        if not tertiary_google_api_key:
            raise ValueError("No Google API Keys found! Please set GOOGLE_API_KEY in .env (comma-separated for multiple).")
        if not quaternary_google_api_key:
            raise ValueError("No Google API Keys found! Please set GOOGLE_API_KEY in .env (comma-separated for multiple).")

        # Define transient errors to retry
        transient_errors = (
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
            google_exceptions.InternalServerError,
            google_exceptions.Aborted,
            google_exceptions.Unknown,
            google_exceptions.ResourceExhausted, # Added for quota issues
        )

        self._retry_config = {
            "retry_if_exception_type": transient_errors,
            "wait_exponential_jitter": True, 
            "stop_after_attempt": settings.LLM_MAX_RETRIES, 
            "exponential_jitter_params": {
                "initial": 0.1,
                "max": 1.0,
                "jitter": 0.25
            }
        }

        # Initialize models for each model tier
        self._primary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_PRIMARY_MODEL,
            api_key=primary_google_api_key,
            temperature=0.0,
            timeout=settings.LLM_TIMEOUT
        )
        
        self._secondary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_SECONDARY_MODEL,
            api_key=secondary_google_api_key,
            temperature=0.0,
            timeout=settings.LLM_TIMEOUT
        ) 
        
        self._tertiary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_TERTIARY_MODEL,
            api_key=tertiary_google_api_key,
            temperature=0.0,
            timeout=settings.LLM_TIMEOUT
        )
        
        self._quaternary_model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_QUATERNARY_MODEL,
            api_key=quaternary_google_api_key,
            temperature=0.0,
            timeout=settings.LLM_TIMEOUT
        )

        logger.info(f"""
            LLMService ready |
            Primary: {settings.GEMINI_PRIMARY_MODEL} |
            Secondary: {settings.GEMINI_SECONDARY_MODEL} |
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
    
    