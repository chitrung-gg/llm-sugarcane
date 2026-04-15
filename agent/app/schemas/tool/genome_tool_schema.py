from typing import Optional
from pydantic import BaseModel, Field


class GeneListInput(BaseModel):
    genome_id: int = Field(..., description="Genome identifier")
    page: int = Field(1, ge=1, description="Page number (>=1)")
    limit: int = Field(20, ge=1, le=100, description="Items per page (1-100)")

class GeneSearchInput(BaseModel):
    genome_id: Optional[int] = None
    keyword: Optional[str] = None
    chromosome: Optional[str] = None
    gene_id_exact: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=50)

class BlastInput(BaseModel):
    genome_id: int
    sequence: str
    # program: str = "blastn" # blastn, blastp...
    evalue: float = 1e-5

# class SyntenyInput(BaseModel):
#     genome_a_id: int
#     genome_b_id: int
#     start_a: Optional[int] = None
#     end_a: Optional[int] = None
#     start_b: Optional[int] = None
#     end_b: Optional[int] = None
#     check_quality: bool = True

class SyntenyHaplotypeInput(BaseModel):
    genome_id: int
    haplotype_set_query: str
    haplotype_set_subject: str
    homologous_group: Optional[int] = None

class PrimerDesignInput(BaseModel):
    genome_id: int
    query: str
    primer_num_return: int = 20
    primer_product_size_range: str = "100-400"
    primer_opt_size: int = 20
    primer_min_size: int = 18
    primer_max_size: int = 24
    primer_opt_tm: float = 60
    primer_min_tm: float = 52
    primer_max_tm: float = 68
    primer_min_gc: float = 20
    primer_max_gc: float = 80
    primer_opt_gc_percent: float = 50
