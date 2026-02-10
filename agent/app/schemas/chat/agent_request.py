from typing import Optional
from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    query: str = Field(..., description="Question for Agent")
    context_data: Optional[str] = Field(None, description="Optional metadata/context")

