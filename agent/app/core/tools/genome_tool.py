from typing import Optional, List, Dict, Any
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.services.tools.genome_http_client import call_backend
from app.schemas.tool.genome_tool_schema import BlastInput, GeneListInput, GeneSearchInput, PrimerDesignInput, SyntenyInput

@tool
async def list_genome_files() -> Dict[str, Any]:
    """
    List all available genome files and their metadata in the database. 
    CRITICAL: Use this tool FIRST whenever the user asks about a genome, genome files, or needs to run an analysis, because you must find the correct 'genome_id' or 'file_id' from this list to use in subsequent tools.
    """
    return await call_backend("GET", "/api/genome/files")

@tool
async def get_region_sequence(file_id: int, chrom: str, start: int, end: int) -> Dict[str, Any]:
    """
    Retrieve a simplified list of all registered genomes (Name, Genotype, Status, ID).
    Use this if you just need to quickly look up a genome's basic ID by its name.
    """
    params = {"file_id": file_id, "chrom": chrom, "start": start, "end": end}
    return await call_backend("GET", "/api/genome/region/sequence", params=params)

@tool
async def get_region_annotation(file_id: int, chrom: str, start: int, end: int) -> Dict[str, Any]:
    """
    Retrieve the raw genomic sequence for a specific chromosomal region.
    Requires 'file_id' (obtainable from list_genome_files), 'chrom' (chromosome name), 'start' position, and 'end' position.
    """
    params = {"file_id": file_id, "chrom": chrom, "start": start, "end": end}
    return await call_backend("GET", "/api/genome/region/annotation", params=params)

@tool(args_schema=GeneListInput)
async def get_genes_list(genome_id: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
    """
    Retrieve all gene annotations and features located within a specific chromosomal region.
    Requires 'file_id' (obtainable from list_genome_files), 'chrom' (chromosome name), 'start', and 'end'.
    """
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
    """
    Perform an advanced search to find specific genes based on keyword, exact gene ID, or coordinate ranges.
    Use this tool when the user asks to "find a gene", "search for genes", or look up a gene by its name/locus.
    Highly recommended to provide 'genome_id' alongside the search criteria.
    """
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
    """
    Retrieve comprehensive details for ONE specific gene, including its chromosome, coordinates, and full sequences (genomic, CDS, protein, flanks).
    Use this when the user asks for details, properties, or sequences of a specific gene.
    Requires BOTH 'gene_id' (e.g., Soffi...) and 'genome_id'.
    """
    params = {"genome_id": genome_id}
    return await call_backend("GET", f"/api/genome/detail/{gene_id}", params=params)

@tool
async def get_sequence_raw(genome_id: int, gene_id: str, type: str = "genomic") -> Dict[str, Any]:
    """
    Quickly retrieve ONLY the raw string sequence for a gene.
    Requires 'genome_id', 'gene_id', and 'type' (must be one of: "genomic", "cds", "protein", "flank").
    """
    params = {"genome_id": genome_id, "gene_id": gene_id, "type": type}
    return await call_backend("GET", "/api/genome/sequence", params=params)

@tool(args_schema=BlastInput)
async def run_blast(file_id: int, sequence: str, program: str = "blastn", evalue: float = 1e-5) -> Dict[str, Any]:
    """
    Run a BLAST alignment against a specific genome.
    Use this when the user provides a nucleotide or protein sequence and wants to align it.
    Requires 'file_id' (the target database) and 'sequence' (the query).
    """
    payload = {"file_id": file_id, "sequence": sequence, "program": program, "evalue": evalue}
    return await call_backend("POST", "/api/blast/run", json_data=payload)

@tool(args_schema=SyntenyInput)
async def run_synteny_analysis(
    genome_a_id: int, genome_b_id: int,
    start_a: Optional[int] = None, end_a: Optional[int] = None,
    start_b: Optional[int] = None, end_b: Optional[int] = None,
    check_quality: bool = True,
) -> Dict[str, Any]:
    """
    Perform synteny block analysis to compare the structure of two different genomes.
    Requires BOTH 'genome_a_id' and 'genome_b_id'. Optional coordinates can focus the analysis on specific regions.
    """
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
    """
    Run the CRISPOR tool to design gRNA candidates and analyze off-target effects.
    Requires 'genome_id'. You must also provide EITHER a 'gene_id' or a raw 'sequence'.
    """
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
    """
    Design PCR primers specifically optimized for complex polyploid genomes.
    Requires 'file_id' and a target 'query'.
    """
    payload = {
        "file_id": file_id, "query": query, "primer_num_return": primer_num_return,
        "primer_product_size_range": primer_product_size_range, "primer_opt_size": primer_opt_size,
        "primer_min_size": primer_min_size, "primer_max_size": primer_max_size,
        "primer_opt_tm": primer_opt_tm, "primer_min_tm": primer_min_tm, "primer_max_tm": primer_max_tm,
        "primer_min_gc": primer_min_gc, "primer_max_gc": primer_max_gc, "primer_opt_gc_percent": primer_opt_gc_percent
    }
    return await call_backend("POST", "/api/primer/design_polyploid", json_data=payload)