from typing import List, Literal

from pydantic import BaseModel, Field

# Pydantic Models for Structured Output

class SynthesizerDecision(BaseModel):
    is_complete: bool = Field(
        description="True if the provided context is sufficient to fully answer the user's query."
    )
    final_answer: str = Field(
        description="The final comprehensive answer, or the reasoning for why more information is needed."
    )

# Workflow
