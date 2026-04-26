from typing import Literal, TypedDict

from app.common.constants import RecordSourceType

class RecordSource(TypedDict):
    """Tracks where a piece of information came from for debugging and citation."""
    source_type: RecordSourceType
    origin: str
    content: str
    metadata: dict