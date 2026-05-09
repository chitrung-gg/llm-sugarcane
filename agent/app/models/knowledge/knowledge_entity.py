from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional
import uuid

from sqlmodel import Column, Field, Relationship, SQLModel, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.common.constants import SYSTEM_OWNER_ID


class KnowledgeEntity(SQLModel, table=True):
    """Replaces global_markers. Stores universal traits, diseases, and genes."""
    __tablename__: ClassVar[Any] = "knowledge_entities"
    __table_args__ = (
        UniqueConstraint("name", "owner_id", name="unique_name_per_owner"),
    )
    
    global_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    entity_type: str = Field(description="'Gene', 'Trait', 'Disease', 'Tissue'")
    reference_sequence: Optional[str] = None
    
    # Ownership and Privacy
    owner_id: uuid.UUID = Field(default=SYSTEM_OWNER_ID, index=True, description="UUID of the user or SYSTEM_OWNER_ID")
    is_public: bool = Field(default=False, index=True)

    # LLM Parser inserts raw NCBI / Biological context here
    knowledge_entities_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    created_at: datetime = Field(default_factory=datetime.now)