from typing import Optional, List
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

class CompareGenomesInput(BaseModel):
    ids: str = Field(..., description="Comma-separated list of Genome IDs to compare")

class GenomeAnalysisInput(BaseModel):
    id: int = Field(..., description="Genome ID")
    force_refresh: bool = Field(False, description="Force Refresh")

class ChromosomeDetailInput(BaseModel):
    id: int = Field(..., description="Genome ID")
    name: str = Field(..., description="Chromosome Name")

class CrossVarietySearchInput(BaseModel):
    ids: str = Field(..., description="Comma-separated Genome IDs")
    keyword: str = Field(..., description="Search keyword (e.g., 'sucrose')")
    limit: int = Field(50, description="Limit")

class CompareNeighborhoodsInput(BaseModel):
    gid_a: int = Field(..., description="Genome A ID")
    region_a: str = Field(..., description="Region A (e.g. Chr1:100-200)")
    gid_b: int = Field(..., description="Genome B ID")
    region_b: str = Field(..., description="Region B (e.g. Chr1:300-400)")

class GeneAllelesInput(BaseModel):
    id: int = Field(..., description="Genome ID")
    gene_id: str = Field(..., description="Gene ID")

class GeneStructureInput(BaseModel):
    id: int = Field(..., description="Genome ID")
    gene_id: str = Field(..., description="Gene ID")

class GenePromoterInput(BaseModel):
    id: int = Field(..., description="Genome ID")
    gene_id: str = Field(..., description="Gene ID")
    kb: int = Field(2, description="Number of kilobases upstream to fetch")

class BatchSequencesInput(BaseModel):
    id: int = Field(..., description="Genome ID")
    type: str = Field("genomic", description="Type of sequence (genomic, cds, protein)")
    gene_ids: List[str] = Field(..., description="List of Gene IDs")

class InvestigateRegionInput(BaseModel):
    genome_id: int = Field(..., description="Genome ID")
    chrom: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Start position")
    end: int = Field(..., description="End position")
    limit: int = Field(50, description="Limit")

class RegionSequenceInput(BaseModel):
    genome_id: int = Field(..., description="Genome ID")
    chrom: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Start position")
    end: int = Field(..., description="End position")

class PaginationInput(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(50, ge=1, le=100, description="Page size")
