from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional
import uuid

from sqlmodel import Column, Field, Relationship, SQLModel
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from app.models.user.user_dataset import UserDataset
    
class UserProject(SQLModel, table=True):
    """Container for multiple datasets, representing a study or experiment."""
    __tablename__: ClassVar[Any] = "user_projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # Names are just labels now, not structural keys
    name: str = Field(index=True) 
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    dataset_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )

    # SQLAlchemy Relationship: A project has many datasets
    datasets: List["UserDataset"] = Relationship(
        back_populates="project",
        cascade_delete=True # If a project is deleted, delete its datasets
    )