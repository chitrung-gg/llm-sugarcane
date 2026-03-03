# import os
# from typing import Dict, List, Literal

# from pydantic import BaseModel, Field

# """
#     Abstract the different LLM from different vendors
#     LLM generate human-like text via deep, context-aware understanding
    
# # Reasoning Effort compare between OpenAI and Gemini: https://ai.google.dev/gemini-api/docs/openai
# """
# class BaseLLM(BaseModel):
#     reasoning_effort: Dict[str, List[str]] = Field(
#         default_factory = lambda: {
#             "gemini": ["minimal", "low"],
#             "openai": ["low", "medium", "high"],
#         }
#     )

#     def generate(self, prompt: str) -> str:
#         raise NotImplementedError("Subclasses must implement generate()")


        