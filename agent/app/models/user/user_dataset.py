from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional
import uuid

from matplotlib.rcsetup import validate_string
from sqlalchemy import Enum
from sqlmodel import Column, Field, Relationship, SQLModel
from sqlalchemy.dialects.postgresql import JSONB

from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType

from app.models.user.knowledge_file_link import KnowledgeFileLink

if TYPE_CHECKING:
    from app.models.user.user_project import UserProject
    
class UserDataset(SQLModel, table=True):
    """Represents a Cultivar or specific biological entity container."""
    __tablename__: ClassVar[Any] = "user_datasets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="user_projects.id", index=True)
    
    name: str = Field(index=True)  # e.g., "Cultivar R570"
    description: Optional[str] = None
    
    # Stores custom properties (Tissue, Condition, etc.)
    dataset_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    is_public: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.now)

    # 🌟 SQLAlchemy Relationships
    project: Optional["UserProject"] = Relationship(back_populates="datasets")
    files: List["UserDatasetFile"] = Relationship(
        back_populates="dataset", 
        cascade_delete=True
    )

class UserDatasetFile(SQLModel, table=True):
    """Individual files belonging to a Cultivar (e.g., its GFF3, FASTA, etc.)."""
    __tablename__: ClassVar[Any] = "user_dataset_files"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dataset_id: uuid.UUID = Field(foreign_key="user_datasets.id", index=True)
    
    file_name: str
    file_type: IngestionSourceType = Field(
        sa_column=Column(Enum(IngestionSourceType, validate_strings=True))
    )
    rustfs_uri: str

    file_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )

    genome_global_id: Optional[uuid.UUID] = Field(default=None, index=True)
    
    knowledge_links: List[KnowledgeFileLink] = Relationship(
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    created_at: datetime = Field(default_factory=datetime.now)

    dataset: Optional[UserDataset] = Relationship(back_populates="files")

    model_config = {"use_enum_values": True}
