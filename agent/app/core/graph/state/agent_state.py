import operator
import uuid
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document

from app.common.constants import (
    AgentIntent,
    ToolExecutionStatus,
    UploadedFileType,
)
from app.core.graph.state.record_source import RecordSource

class UploadedFile(TypedDict):
    """Stores users' uploaded files metadata."""
    file_id: str
    file_name: str
    file_path: Optional[str]
    file_type: UploadedFileType
    description: Optional[str]
    local_content: Optional[str] # Direct text/sequence content for small files
    rustfs_uri: Optional[str]    # S3/RustFS URI for large genomic files

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

class DatasetContext(TypedDict):
    """Stores pre-registered backend genomic datasets (Cultivars)."""
    dataset_id: str
    is_user_uploaded: bool     # Tells the tool which DB table to check
    dataset_name: str          # e.g., "R570" or "ZZ1"
    fasta_uri: Optional[str]   # s3://.../r570.fasta.gz
    gff3_uri: Optional[str]    # s3://.../r570.gff3.gz
    protein_uri: Optional[str] # s3://.../r570.pep.gz

class AgentState(TypedDict):
    # Core
    query: str
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str # Stores the rolling summary of the conversation
    uploaded_files: Annotated[List[UploadedFile], operator.add]
    uploaded_chunks: Annotated[List[Document], operator.add]
    file_context: str # Extracted content from uploaded files

    # --- Hierarchy & Organization ---
    active_project_name: Optional[str] 
    active_datasets: List[DatasetContext]

    # Routing
    intent: AgentIntent
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
    
    # Metadata
    execution_id: Optional[uuid.UUID] # Correlation ID for the current request-response cycle

    # Final
    final_answer: str
    is_complete: bool
