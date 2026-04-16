import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document

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

class WebResult(TypedDict):
    """Stores the web result from search tool"""
    snippet: str
    title: str
    link: str
    engines: list[str]
    category: str


class ToolResult(TypedDict):
    """Stores tool executions' results."""
    tool_name: str
    args: Dict[str, Any]
    status: Literal["success", "error"]
    output: str 
    execution_time_ms: Optional[int] 

class AgentState(TypedDict):
    # Core
    query: str
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str # Stores the rolling summary of the conversation
    uploaded_files: List[UploadedFile]
    uploaded_chunks: Annotated[List[Document], operator.add]

    # Routing
    intent: Literal["rag_only", "tool_only", "web_search", "all", "unclear", "direct_answer"]
    required_tools: List[str]

    # Execution tracking
    rag_results: Annotated[List[RAGResult], operator.add]
    tool_results: Annotated[List[ToolResult], operator.add] 
    web_results: Annotated[List[WebResult], operator.add]
    extracted_knowledge: Annotated[List[Dict[str, Any]], operator.add]
    iteration_count: int
    max_iterations: int         # Circuit breaker
    last_intent: str
    router_guidance: str

    # Source tracking - will be populated by each node
    sources_used: List[RecordSource]
    
    # Final
    final_answer: str
    is_complete: bool

