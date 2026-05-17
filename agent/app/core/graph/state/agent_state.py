import operator
import uuid
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document

from app.schemas.tool.tool_call_request import ToolCallRequest
from app.common.constants import (
    AgentIntent,
    ToolExecutionStatus,
    UploadedFileType,
)
from app.core.graph.state.record_source import RecordSource

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
    status: ToolExecutionStatus
    output: str 
    execution_time_ms: Optional[int] 

class AgentFile(TypedDict):
    """A unified file representation for both Genomic and Knowledge files."""
    file_id: str
    file_name: str
    file_category: Literal["GENOMIC", "KNOWLEDGE"] # Helps the LLM know which tools to use
    file_type: str # e.g., "FASTA", "GFF3", "PDF", "TXT"
    rustfs_uri: str
    local_content: Optional[str] # Direct text for very small TXT/CSV files

class AgentDataset(TypedDict):
    """A single dataset containing its specific genomic and knowledge files."""
    dataset_id: str
    dataset_name: str
    source: Literal["USER_WORKSPACE", "SYSTEM_LIBRARY"] # Helps the LLM understand ownership
    
    # Splitting them makes it MUCH easier for the LLM's Planner to read 
    genomic_files: List[AgentFile]
    knowledge_files: List[AgentFile]

class AgentProject(TypedDict):
    """The overarching biological context for the current conversation."""
    project_id: str
    project_name: str
    description: Optional[str]
    # Useful if you store global parameters like {"target_organism": "Saccharum officinarum"}
    metadata: Optional[Dict[str, Any]]

class AgentState(TypedDict):
    # Core
    query: str
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str # Stores the rolling summary of the conversation
    # uploaded_chunks: Annotated[List[Document], operator.add]

    # --- Hierarchy & Organization ---
    active_project: Optional[AgentProject]
    active_datasets: Optional[List[AgentDataset]]
    # system_datasets: Optional[List[AgentDataset]]

    # Plan state (for inner agent visibility)
    past_steps: List[Any] 

    # Routing
    intent: AgentIntent
    required_tools: List[ToolCallRequest]
    rag_query: Optional[str] # Pre-optimized query for Vector DB
    web_query: Optional[str] # Pre-optimized query for Web Search

    # Execution tracking
    rag_results: Annotated[List[RAGResult], operator.add]
    tool_results: Annotated[List[ToolResult], operator.add] 
    web_results: Annotated[List[WebResult], operator.add]
    extracted_knowledge: List[Dict[str, Any]]
    iteration_count: int
    max_iterations: int         # Circuit breaker
    last_intent: str
    router_guidance: str

    # Source tracking - will be populated by each node
    sources_used: List[RecordSource]
    
    # Metadata
    execution_id: Optional[uuid.UUID] # Correlation ID for the current request-response cycle

    # Final
    final_answer: str
    is_complete: bool
