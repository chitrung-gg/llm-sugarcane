from typing import List, Optional
import uuid
from pydantic import BaseModel, Field

class RAGSourceItem(BaseModel):
    """Schema for consolidated RAG sources returned to the frontend."""
    source_file: str
    chunks_used: int = 1
    highest_score: Optional[float] = None

class ToolExecutionItem(BaseModel):
    """Schema for individual tool executions returned to the frontend."""
    tool_name: str
    status: str
    output: str
    execution_time_ms: Optional[int] = None

class AgentResponse(BaseModel):
    """Main response schema for the Agent API."""
    thread_id: uuid.UUID
    answer: str
    rag_sources: List[RAGSourceItem] = Field(default_factory=list)
    tool_executions: List[ToolExecutionItem] = Field(default_factory=list)
    execution_time: float