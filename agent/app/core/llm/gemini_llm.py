import os

from typing import Literal, Optional
from pydantic import Field, PrivateAttr, SecretStr, model_validator
from google import genai

from app.core.llm.base_llm import BaseLLM


class GeminiLLM(BaseLLM):
    provider: Literal["gemini"] = "gemini"
    model_name: str = "gemini-3-flash-preview"
    api_key: SecretStr | None = Field(
        default_factory=lambda: (
            SecretStr(v) if (v := os.getenv("GOOGLE_API_KEY")) else None
        )
    )

    _client: Optional[genai.Client] = PrivateAttr(default=None)

    @model_validator(mode="after")
    def setup_gemini_client(self):
        if self.api_key:
            self._client = genai.Client(api_key=self.api_key.get_secret_value())
        return self

    def generate(self, prompt: str) -> str:
        if not self._client:
            raise ValueError("Gemini API Key is not configured!")
        
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            if response.text:
                return response.text
            return ""
        except Exception as e:
            raise RuntimeError(f"Error when calling Google API: {str(e)}")