import uuid
from typing import Optional, List
from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    query: str = Field(..., description="Question for Agent")
    context_data: Optional[str] = Field(None, description="Optional metadata/context")
    project_id: Optional[uuid.UUID] = Field(None, description="Persistent project ID")
    dataset_ids: Optional[List[uuid.UUID]] = Field(default_factory=list, description="Specific datasets to load")
