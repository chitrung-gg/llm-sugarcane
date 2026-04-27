# from typing import Any, ClassVar, Dict, Optional, cast
# import uuid

# from sqlmodel import Column, Field, SQLModel
# from sqlalchemy.dialects.postgresql import JSONB
# from sqlalchemy.orm import declared_attr


# class GenomeModel(SQLModel, table=True):
#     __tablename__: ClassVar[Any] = "genomes"        # Class Config
    
#     id: Optional[int] = Field(default=None, primary_key=True)
#     global_id: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True)
    
#     name: str = Field(index=True)
#     genotype: Optional[str] = None
#     fasta_path: Optional[str] = None
#     gff_path: Optional[str] = None
#     blast_db_path: Optional[str] = None
#     status: str
    
#     genome_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))