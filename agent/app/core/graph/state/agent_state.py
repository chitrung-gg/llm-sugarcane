import operator
from typing import Annotated, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

from app.core.graph.state.record_source import RecordSource

class UploadedFile(TypedDict):
    """Stores users' uploaded files metadata."""
    file_id: str
    file_name: str
    file_path: str
    file_type: Literal["pdf", "md", "fasta", "json", "unknown"]
    description: Optional[str] 

class RAGResult(TypedDict):
    """Stores the extracted result from Vector Database."""
    content: str
    source_file: str 
    page_number: Optional[int]
    relevance_score: Optional[float]        # Cosine

class ToolResult(TypedDict):
    """Stores tool executions' results."""
    tool_name: str
    status: Literal["success", "error"]
    output: str 
    execution_time_ms: Optional[int] 

class AgentState(TypedDict):
    # Core
    query: str
    messages: Annotated[List[BaseMessage], add_messages]
    uploaded_files: List[UploadedFile]

    # Routing
    intent: Literal["rag_only", "tool_only", "both", "unclear"]
    required_tools: List[str]

    # Execution tracking
    rag_results: Annotated[List[RAGResult], operator.add]
    tool_results: Annotated[List[ToolResult], operator.add] 
    iteration_count: int
    max_iterations: int         # Circuit breaker

    # Source tracking - will be populated by each node
    sources_used: List[RecordSource]
    
    # Final
    final_answer: str
    is_complete: bool

