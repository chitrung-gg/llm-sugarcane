from typing import Optional, List, Dict, Any
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.services.tools.genome_http_client import call_backend
from app.schemas.tool.genome_tool_schema import BlastInput, GeneListInput, GeneSearchInput, PrimerDesignInput, SyntenyInput

@tool
async def list_genome_files() -> Dict[str, Any]:
    """List available genome files."""
    return await call_backend("GET", "/api/genome/files")

@tool
async def get_region_sequence(file_id: int, chrom: str, start: int, end: int) -> Dict[str, Any]:
    """Retrieve genomic sequence for a specific region."""
    params = {"file_id": file_id, "chrom": chrom, "start": start, "end": end}
    return await call_backend("GET", "/api/genome/region/sequence", params=params)

@tool
async def get_region_annotation(file_id: int, chrom: str, start: int, end: int) -> Dict[str, Any]:
    """Retrieve gene annotations within a genomic region."""
    params = {"file_id": file_id, "chrom": chrom, "start": start, "end": end}
    return await call_backend("GET", "/api/genome/region/annotation", params=params)

# @tool
# async def get_all_genomes() -> List[Dict[str, Any]]:
#     """Retrieve all genomes for dropdown selection."""
#     data = await call_backend("GET", "/api/genome/list")

#     if not isinstance(data, list):
#         raise ValueError("Expected list from /api/genome/list")
    
#     return data

@tool(args_schema=GeneListInput)
async def get_genes_list(genome_id: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
    """Retrieve paginated gene metadata list."""
    payload = {"genome_id": genome_id, "page": page, "limit": limit}
    return await call_backend("POST", "/api/genome/get-genes", json_data=payload)

@tool(args_schema=GeneSearchInput)
async def search_genes_full(
    genome_id: Optional[int] = None,
    keyword: Optional[str] = None,
    chromosome: Optional[str] = None,
    gene_id_exact: Optional[str] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    page: int = 1,
    limit: int = 10,
) -> Dict[str, Any]:
    """Perform advanced gene search."""
    # Drop None values to keep the payload clean
    payload = {
        k: v for k, v in {
            "genome_id": genome_id, "keyword": keyword, "chromosome": chromosome,
            "gene_id_exact": gene_id_exact, "start": start, "end": end,
            "page": page, "limit": limit
        }.items() if v is not None
    }
    return await call_backend("POST", "/api/genome/search", json_data=payload)

@tool
async def get_gene_detail(gene_id: str, genome_id: int) -> Dict[str, Any]:
    """Retrieve detailed information for a gene."""
    params = {"genome_id": genome_id}
    return await call_backend("GET", f"/api/genome/detail/{gene_id}", params=params)

@tool
async def get_sequence_raw(genome_id: int, gene_id: str, type: str = "genomic") -> Dict[str, Any]:
    """Retrieve raw sequence for a gene."""
    params = {"genome_id": genome_id, "gene_id": gene_id, "type": type}
    return await call_backend("GET", "/api/genome/sequence", params=params)

@tool(args_schema=BlastInput)
async def run_blast(file_id: int, sequence: str, program: str = "blastn", evalue: float = 1e-5) -> Dict[str, Any]:
    """Run BLAST alignment."""
    payload = {"file_id": file_id, "sequence": sequence, "program": program, "evalue": evalue}
    return await call_backend("POST", "/api/blast/run", json_data=payload)

@tool(args_schema=SyntenyInput)
async def run_synteny_analysis(
    genome_a_id: int, genome_b_id: int,
    start_a: Optional[int] = None, end_a: Optional[int] = None,
    start_b: Optional[int] = None, end_b: Optional[int] = None,
    check_quality: bool = True,
) -> Dict[str, Any]:
    """Perform synteny analysis between two genomes."""
    payload = {
        k: v for k, v in {
            "genome_a_id": genome_a_id, "genome_b_id": genome_b_id,
            "start_a": start_a, "end_a": end_a, "start_b": start_b, "end_b": end_b,
            "check_quality": check_quality
        }.items() if v is not None
    }
    return await call_backend("POST", "/api/synteny/analyze", json_data=payload)

@tool
async def run_crispor(genome_id: int, gene_id: Optional[str] = None, sequence: Optional[str] = None) -> Dict[str, Any]:
    """Run CRISPOR gRNA design and off-target analysis."""
    # Note: OpenAPI spec says POST, but parameters are 'query' (in)
    params = {k: v for k, v in {"genome_id": genome_id, "gene_id": gene_id, "sequence": sequence}.items() if v is not None}
    return await call_backend("POST", "/api/crispor", params=params)

@tool(args_schema=PrimerDesignInput)
async def design_polyploid_primer(
    file_id: int, query: str, primer_num_return: int = 20,
    primer_product_size_range: str = "100-400", primer_opt_size: int = 20,
    primer_min_size: int = 18, primer_max_size: int = 24,
    primer_opt_tm: float = 60, primer_min_tm: float = 52, primer_max_tm: float = 68,
    primer_min_gc: float = 20, primer_max_gc: float = 80, primer_opt_gc_percent: float = 50,
) -> Dict[str, Any]:
    """Design primers for polyploid genomes."""
    payload = {
        "file_id": file_id, "query": query, "primer_num_return": primer_num_return,
        "primer_product_size_range": primer_product_size_range, "primer_opt_size": primer_opt_size,
        "primer_min_size": primer_min_size, "primer_max_size": primer_max_size,
        "primer_opt_tm": primer_opt_tm, "primer_min_tm": primer_min_tm, "primer_max_tm": primer_max_tm,
        "primer_min_gc": primer_min_gc, "primer_max_gc": primer_max_gc, "primer_opt_gc_percent": primer_opt_gc_percent
    }
    return await call_backend("POST", "/api/primer/design_polyploid", json_data=payload)