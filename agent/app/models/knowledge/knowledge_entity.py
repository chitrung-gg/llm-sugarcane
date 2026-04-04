from datetime import datetime
from typing import Any, ClassVar, Dict, Optional
import uuid

from sqlmodel import Column, Field, SQLModel
from sqlalchemy.dialects.postgresql import JSONB


class KnowledgeEntity(SQLModel, table=True):
    """Replaces global_markers. Stores universal traits, diseases, and genes."""
    __tablename__: ClassVar[Any] = "knowledge_entities"
    
    global_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True, unique=True)
    entity_type: str = Field(description="'Gene', 'Trait', 'Disease', 'Tissue'")
    reference_sequence: Optional[str] = None
    
    # LLM Parser inserts raw NCBI / Biological context here
    knowledge_entities_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    created_at: datetime = Field(default_factory=datetime.now)