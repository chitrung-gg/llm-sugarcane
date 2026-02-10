from typing import Annotated, Union

from pydantic import Field

from app.core.llm.gemini_llm import GeminiLLM

# Initialize Union to instantiate class
LLMModel = Annotated[Union[GeminiLLM], Field(discriminator="provider")]