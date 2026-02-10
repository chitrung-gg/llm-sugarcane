from app.core.llm.gemini_llm import GeminiLLM
from app.services.llm.llm_service import LLMService


def get_llm_service() -> LLMService:
    registry = [
        GeminiLLM()
    ]

    return LLMService(
        model_registry=registry,
        max_retries=3
    )