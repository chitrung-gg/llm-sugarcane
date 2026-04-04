from datetime import datetime
from typing import Any, ClassVar, Optional
import uuid

from sqlmodel import Field, SQLModel


class KnowledgeReference(SQLModel, table=True):
    """Stores Paper data."""
    __tablename__: ClassVar[Any] = "knowledge_references"
    
    global_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True
    )
    title: str
    doi_or_url: Optional[str] = None
    publication_year: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)