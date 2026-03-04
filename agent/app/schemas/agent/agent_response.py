from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.tool.tool_execution import ToolExecution

class RAGSourceItem(BaseModel):
    """Schema for individual RAG sources returned to the frontend."""
    document_id: str
    source_file: str
    chunk_index: int
    score: Optional[float] = None

class ToolExecutionItem(BaseModel):
    """Schema for individual tool executions returned to the frontend."""
    tool_name: str
    status: str
    output: str
    execution_time_ms: Optional[int] = None

class AgentResponse(BaseModel):
    """Main response schema for the Agent API."""
    answer: str
 
    rag_sources: List[RAGSourceItem] = Field(default_factory=list)
    tool_executions: List[ToolExecutionItem] = Field(default_factory=list)
    
    execution_time: float