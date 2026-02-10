from typing import List
from pydantic import BaseModel

from app.core.llm import LLMModel


class LLMService(BaseModel):
    model_registry: List[LLMModel]
    max_retries: int = 3

    def call_with_fallback(self, prompt: str) -> str:
        errors = []
        for model in self.model_registry:
            try:
                print(f"Trying to use model: {getattr(model, 'provider')}")
                return model.generate(prompt)
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                errors.append(error_msg)
                continue
        
        raise RuntimeError(f"Failed to initialize LLMService. Related errors: {errors}")