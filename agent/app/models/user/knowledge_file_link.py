from typing import Any, ClassVar, Optional
import uuid
from sqlmodel import Field, SQLModel

class KnowledgeFileLink(SQLModel, table=True):
    """Link table for Many-to-Many relationship between Files and Knowledge Entities."""
    __tablename__: ClassVar[Any] = "knowledge_file_links"

    # Both form a composite primary key
    file_id: uuid.UUID = Field(foreign_key="user_dataset_files.id", primary_key=True)
    knowledge_entity_id: uuid.UUID = Field(primary_key=True)
    
    # Optional: How confident was the LLM that this file actually talks about this trait?
    relevance_score: Optional[float] = Field(default=None)