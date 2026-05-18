import uuid
from enum import StrEnum
from pathlib import Path
from typing import Final, Set


# --- 0. GLOBAL IDS ---
SYSTEM_OWNER_ID: Final[uuid.UUID] = uuid.UUID("00000000-0000-0000-0000-000000000000")
DEFAULT_USER_ID: Final[uuid.UUID] = uuid.UUID("11111111-1111-1111-1111-111111111111")

# Langgraph
LANGGRAPH_STATE_MAX_ITERATIONS = 3

# Langfuse
LANGFUSE_GRAPH_OBSERVATION_NAME: str = "sugarcane_agent_execution"


# --- 1. MODIFIERS ---
COMPRESSED_SUFFIXES: Final[Set[str]] = {".gz", ".bgz"}

# --- 2. GENOMIC BASES ---
SEQUENCE_BASE: Final[Set[str]] = {".fasta", ".fa", ".fna", ".fastq", ".fq"}
ANNOTATION_BASE: Final[Set[str]] = {".gff", ".gff3", ".gtf"}
VARIANT_BASE: Final[Set[str]] = {".vcf", ".bed"}
ALIGNMENT_BASE: Final[Set[str]] = {".sam", ".bam", ".cram"}
INDEX_BASE: Final[Set[str]] = {".fai", ".bai", ".tbi", ".csi", ".gzi"}

GENOMIC_BASE_EXTENSIONS: Final[Set[str]] = (
    SEQUENCE_BASE | ANNOTATION_BASE | VARIANT_BASE | ALIGNMENT_BASE | INDEX_BASE
)

# Comprehension dynamically creates '.fasta', '.fasta.gz', etc.
GENOMIC_EXTENSIONS: Final[Set[str]] = {
    f"{base}{suffix}" 
    for base in GENOMIC_BASE_EXTENSIONS 
    for suffix in ({""} | COMPRESSED_SUFFIXES)
}

# --- 3. KNOWLEDGE BASES (Docling Supported) ---
DOCUMENT_EXTENSIONS: Final[Set[str]] = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".xlsx", ".xls", ".html", ".epub",
    ".msg", ".eml", ".rtf", ".odt",
    ".md", ".tex", ".csv", ".txt"
}

IMAGE_EXTENSIONS: Final[Set[str]] = {
    ".png", ".jpeg", ".jpg", ".tiff", ".bmp"
}

KNOWLEDGE_EXTENSIONS: Final[Set[str]] = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS


# --- 4. AGENT INTENTS ---
class AgentIntent(StrEnum):
    RAG_ONLY = "rag_only"
    TOOL_ONLY = "tool_only"
    WEB_SEARCH = "web_search"
    ALL = "all"
    UNCLEAR = "unclear"
    DIRECT_ANSWER = "direct_answer"


# --- 5. FILE TYPES ---
class UploadedFileType(StrEnum):
    PDF = "pdf"
    MD = "md"
    FASTA = "fasta"
    JSON = "json"
    GENOMIC_DATASET = "genomic_dataset"
    CONTEXT_DOCUMENT = "context_document"
    UNKNOWN = "unknown"


# --- 6. TOOL STATUS ---
class ToolExecutionStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


# --- 7. SOURCE TYPES ---
class RecordSourceType(StrEnum):
    RAG = "rag"
    TOOL = "tool"
    LLM_INTERNAL = "llm_internal"


# --- 8. PLAN STATUS ---
class PlanStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ObservationType(StrEnum):
    SPAN = "span"
    GENERATION = "generation"
    EMBEDDING = "embedding"
    AGENT = "agent"
    TOOL = "tool"
    CHAIN = "chain"
    RETRIEVER = "retriever"
    EVALUATOR = "evaluator"
    GUARDRAIL = "guardrail"


# --- 9. STREAMING EVENTS ---
class StreamEventType(StrEnum):
    THOUGHT = "thought"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    RAG_RESULT = "rag_result"
    TOKEN = "token"
    ANSWER = "answer"
    INTERRUPT = "interrupt"
    ERROR = "error"
    DONE = "done"


# --- 10. INTERRUPTS & FEEDBACK ---
class InterruptAction(StrEnum):
    APPROVE_PLAN = "APPROVE_PLAN"
    MODIFY_PLAN = "MODIFY_PLAN"

class UserFeedbackAction(StrEnum):
    APPROVE = "APPROVE"
    MODIFY = "MODIFY"

# --- 11. LANGGRAPH EVENT KINDS ---
class EventKind(StrEnum):
    # https://reference.langchain.com/python/langchain-core/runnables/schema/BaseStreamEvent/event
    CHAIN_START = "on_chain_start"
    CHAIN_END = "on_chain_end"
    TOOL_START = "on_tool_start"
    TOOL_END = "on_tool_end"
    CHAT_MODEL_STREAM = "on_chat_model_stream"

class StreamingTag(StrEnum):
    STREAM_PLANNER = "stream_planner"
    STREAM_SYNTHESIZER = "stream_synthesizer"

class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"

class MessageType(StrEnum):
    QUERY = "query"
    ANSWER = "answer"
    THOUGHT = "thought"
    ERROR = "error"

class GraphIngestionAllowedLabels(StrEnum):
    GENE = "gene"
    CULTIVAR = "cultivar"
    PAPER = "paper"
    TRAIT = "trait"
    DISEASE = "disease"
    TISSUE = "tissue"
    ENVIRONMENTAL_STRESS = "environmental_stress"