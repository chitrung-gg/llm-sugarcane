from typing import Literal, TypedDict


class RecordSource(TypedDict):
    """Tracks where a piece of information came from for debugging and citation."""
    source_type: Literal["rag", "tool", "llm_internal"]
    origin: str
    content: str
    metadata: dict