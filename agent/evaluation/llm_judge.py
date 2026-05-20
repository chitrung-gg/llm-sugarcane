import re
from typing import Any, List, Optional, Type

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.runnables import Runnable
from loguru import logger
from deepeval.models.base_model import DeepEvalBaseEmbeddingModel, DeepEvalBaseLLM
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel


from app.configs.settings.settings import get_settings

class DeepEvalEmbedderWrapper(DeepEvalBaseEmbeddingModel):
    def __init__(self):
        settings = get_settings()
        api_key = settings.SECONDARY_GOOGLE_API_KEY if settings.SECONDARY_GOOGLE_API_KEY else None

        _model_name = settings.GEMINI_EMBEDDING_MODEL

        if not api_key:
            raise ValueError("No Google API Keys found! Please set EMBEDDING_GOOGLE_API_KEY in .env.")

        self.model_name = _model_name        
        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=_model_name,
            api_key=api_key
        )

    def load_model(self) -> Any:
        return self._embeddings

    def get_model_name(self):
        return self.model_name

    def embed_text(self, text: str) -> List[float]:
        return self._embeddings.embed_query(text)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return self._embeddings.embed_documents(texts)

    async def a_embed_text(self, text: str) -> List[float]:
        return await self._embeddings.aembed_query(text)

    async def a_embed_texts(self, texts: List[str]) -> List[List[float]]:
        return await self._embeddings.aembed_documents(texts)
    
class GoogleGeminiJudge(DeepEvalBaseLLM):
    def __init__(self, model_name: str):
        settings = get_settings()
        api_key = settings.SECONDARY_GOOGLE_API_KEY.get_secret_value() if settings.SECONDARY_GOOGLE_API_KEY else None

        common_config = {
            "google_api_key": api_key,
            "temperature": 0.0,
            "timeout": settings.LLM_TIMEOUT,  
        }

        # Define transient errors to retry
        transient_errors = (
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
            google_exceptions.InternalServerError,
            google_exceptions.Aborted,
            google_exceptions.Unknown,
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

        if not api_key:
            raise ValueError("Google API Key not found!")
        
        self.model_name_str = model_name
        self.model = ChatGoogleGenerativeAI(
            model=model_name, 
            **common_config
        )
        
    def load_model(self) -> Any:
        return self.model
    
    def get_structured_model(self, schema: Type[BaseModel]) -> Runnable:
        """Returns a primary model configured with structured output AND retry logic."""
        return self.model.with_structured_output(schema).with_retry(**self._retry_config)

    def _clean_and_log(self, prompt: str, raw_output: str) -> str:
        """Logs the raw output and strips markdown to prevent DeepEval JSON crashes."""
        logger.debug(f"[{self.model_name_str} Judge] Prompt Sent:\n{prompt[:200]}...")
        logger.debug(f"[{self.model_name_str} Judge] Raw Output Received:\n{raw_output}")
        
        # Strip markdown code blocks
        cleaned = re.sub(r"```json\s*", "", raw_output, flags=re.IGNORECASE)
        cleaned = re.sub(r"```\s*", "", cleaned)
        return cleaned.strip()

    def generate(self, prompt: str, **kwargs) -> Any:
        # Extract schema from kwargs if it exists
        schema = kwargs.get("schema")
        
        if schema:
            logger.info(f"🚦 [{self.model_name_str} Judge] Calling Synchronously (Structured)...")
            structured_model = self.get_structured_model(schema)
            return structured_model.invoke(prompt)
        else:
            logger.info(f"🚦 [{self.model_name_str} Judge] Calling Synchronously (Text)...")
            res = self.model.invoke(prompt)
            return self._clean_and_log(prompt, str(res.content))

    async def a_generate(self, prompt: str, **kwargs) -> Any:
        # Extract schema from kwargs if it exists
        schema = kwargs.get("schema")
        
        if schema:
            logger.info(f"🚦 [{self.model_name_str} Judge] Calling Asynchronously (Structured)...")
            structured_model = self.get_structured_model(schema)
            return await structured_model.ainvoke(prompt)
        else:
            logger.info(f"🚦 [{self.model_name_str} Judge] Calling Asynchronously (Text)...")
            res = await self.model.ainvoke(prompt)
            return self._clean_and_log(prompt, str(res.content))

    def get_model_name(self):
        return f"Google Gemini ({self.model_name_str})"