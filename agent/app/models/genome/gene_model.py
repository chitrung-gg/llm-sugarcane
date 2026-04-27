# from typing import Any, ClassVar, Dict, Optional
# import uuid

# from sqlmodel import Column, Field, Index, SQLModel
# from sqlalchemy.dialects.postgresql import JSONB


# class Gene(SQLModel, table=True):
#     __tablename__: ClassVar[Any] = "genes"
    
#     id: Optional[int] = Field(default=None, primary_key=True)
#     global_id: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True)
    
#     gene_id: str = Field(index=True)
#     name: Optional[str] = Field(index=True)
#     genome_id: Optional[int] = Field(index=True)
#     chromosome: Optional[str] = None
#     start: Optional[int] = Field(index=True)
#     end: Optional[int] = Field(index=True)
    
#     gene_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    
#     # SOFT LINK: Pure UUID column, no foreign_key strictness
#     knowledge_entity_id: Optional[uuid.UUID] = Field(default=None)