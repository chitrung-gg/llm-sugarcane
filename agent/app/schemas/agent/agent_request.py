import uuid
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field

from app.common.constants import UserFeedbackAction


class AgentRequest(BaseModel):
    query: str = Field(..., description="Question for Agent")
    context_data: Optional[str] = Field(None, description="Optional metadata/context")
    project_id: Optional[uuid.UUID] = Field(None, description="Persistent project ID")
    dataset_ids: Optional[List[uuid.UUID]] = Field(default_factory=list, description="Specific datasets to load")

class HumanFeedbackPayload(BaseModel):
    """Schema for handling human-in-the-loop responses."""
    action: UserFeedbackAction = Field(..., description="APPROVE or MODIFY")
    feedback: Optional[str] = Field(None, description="Text instructions from the user to the LLM")
    modified_plan: Optional[List[Dict[str, Any]]] = Field(None, description="The exact edited plan from the UI visualizer")

class ChatStreamRequest(BaseModel):
    """The overarching request payload from the frontend."""
    thread_id: uuid.UUID
    query: Optional[str] = None
    human_feedback: Optional[HumanFeedbackPayload] = None
    project_id: Optional[uuid.UUID] = None
    dataset_ids: Optional[List[uuid.UUID]] = Field(default_factory=list)