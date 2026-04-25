from typing import Optional, List, Dict, Any
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.core.tools.registry.registry_tool import register_agent_tool
from app.services.tools.call_genome_backend import call_genome_backend
from app.schemas.tool.genome_tool_schema import (
    BlastInput, GeneListInput, GeneSearchInput, PrimerDesignInput, SyntenyHaplotypeInput,
    CompareGenomesInput, GenomeAnalysisInput, ChromosomeDetailInput, CrossVarietySearchInput,
    CompareNeighborhoodsInput, GeneAllelesInput, GeneStructureInput, GenePromoterInput,
    BatchSequencesInput, InvestigateRegionInput, RegionSequenceInput, PaginationInput
)

@register_agent_tool
@tool
async def list_genome_files() -> Dict[str, Any]:
    """
    Retrieve the complete list of all genome files currently available in the system database,
    including their metadata, status, identifiers, and associated file paths.

    Use this tool FIRST whenever a task involves genomes, sequences, or analysis,
    in order to obtain the correct `id` (genome_id/file_id) for downstream tools.

    Returns a list of genome records, each containing fields such as:
    - id: unique identifier (required for later tool calls)
    - name: genome or chromosome name
    - fasta_path, gff_path, cds_path, protein_path: file locations
    - status: processing status (e.g., READY)
    - index_path, blast_db_path: auxiliary data if available
    """
    return await call_genome_backend("GET", "/api/genome/files")

# @register_agent_tool 
# @tool
# async def get_region_sequence(file_id: int, chrom: str, start: int, end: int) -> Dict[str, Any]:
#     """
#     Retrieve a simplified list of all registered genomes (Name, Genotype, Status, ID).
#     Use this if you just need to quickly look up a genome's basic ID by its name.
#     """
#     params = {"file_id": file_id, "chrom": chrom, "start": start, "end": end}
#     return await call_genome_backend("GET", "/api/genome/region/sequence", params=params)

# @register_agent_tool 
# @tool
# async def get_region_annotation(file_id: int, chrom: str, start: int, end: int) -> Dict[str, Any]:
#     """
#     Retrieve the raw genomic sequence for a specific chromosomal region.
#     Requires 'file_id' (obtainable from list_genome_files), 'chrom' (chromosome name), 'start' position, and 'end' position.
#     """
#     params = {"file_id": file_id, "chrom": chrom, "start": start, "end": end}
#     return await call_genome_backend("GET", "/api/genome/region/annotation", params=params)

@register_agent_tool
@tool(args_schema=CompareGenomesInput)
async def compare_genomes(ids: str) -> Dict[str, Any]:
    """
    Expert Tool: Compare multiple genomes side-by-side.
    Requires a comma-separated list of Genome IDs.
    """
    params = {"ids": ids}
    return await call_genome_backend("GET", "/api/genome/compare", params=params)

@register_agent_tool
@tool(args_schema=GenomeAnalysisInput)
async def get_genome_analysis(id: int, force_refresh: bool = False) -> Dict[str, Any]:
    """
    High-level analysis landscape of a genome (assembly stats, feature counts, protein/cds stats).
    """
    params = {"force_refresh": force_refresh}
    return await call_genome_backend("GET", f"/api/genome/{id}/analysis", params=params)

@register_agent_tool
@tool(args_schema=ChromosomeDetailInput)
async def get_chromosome_detail(id: int, name: str) -> Dict[str, Any]:
    """
    Granular details about a specific chromosome in a genome.
    """
    return await call_genome_backend("GET", f"/api/genome/{id}/chromosomes/{name}")

@register_agent_tool
@tool
async def get_subgenome_bias(id: int) -> Dict[str, Any]:
    """
    Expert Tool: Analyze gene distribution across A, B, C, D, E, F sub-genomes.
    """
    return await call_genome_backend("GET", f"/api/genome/{id}/subgenome-bias")

@register_agent_tool
@tool
async def get_functional_distribution(id: int) -> Dict[str, Any]:
    """
    Expert Tool: Aggregate genes into high-level biological categories.
    """
    return await call_genome_backend("GET", f"/api/genome/{id}/functional-distribution")

@register_agent_tool
@tool(args_schema=CrossVarietySearchInput)
async def cross_variety_search(ids: str, keyword: str, limit: int = 50) -> Dict[str, Any]:
    """
    Priority 1: Search for genes/traits across multiple varieties.
    ids: Comma-separated Genome IDs.
    keyword: Search keyword (e.g., 'sucrose').
    """
    params = {"ids": ids, "keyword": keyword, "limit": limit}
    return await call_genome_backend("GET", "/api/genome/cross-search", params=params)

@register_agent_tool
@tool(args_schema=CompareNeighborhoodsInput)
async def compare_neighborhoods(gid_a: int, region_a: str, gid_b: int, region_b: str) -> Dict[str, Any]:
    """
    Priority 2: Compare genomic feature order in two locations side-by-side.
    region_a/b: Genomic range (e.g., 'Chr1:100-200').
    """
    params = {"gid_a": gid_a, "region_a": region_a, "gid_b": gid_b, "region_b": region_b}
    return await call_genome_backend("GET", "/api/genome/compare-neighborhoods", params=params)

@register_agent_tool
@tool(args_schema=GeneAllelesInput)
async def get_gene_alleles(id: int, gene_id: str) -> Dict[str, Any]:
    """
    Expert Tool: Find versions of this gene across other sub-genomes (alleles).
    """
    return await call_genome_backend("GET", f"/api/genome/{id}/alleles/{gene_id}")

@register_agent_tool
@tool(args_schema=GeneStructureInput)
async def get_gene_structure(id: int, gene_id: str) -> Dict[str, Any]:
    """
    Expert Tool: Deep analysis of gene architecture (exons/introns).
    """
    return await call_genome_backend("GET", f"/api/genome/{id}/gene-structure/{gene_id}")

@register_agent_tool
@tool(args_schema=GenePromoterInput)
async def get_gene_promoter(id: int, gene_id: str, kb: int = 2) -> Dict[str, Any]:
    """
    Expert Tool: Fetch the promoter (upstream) sequence for a specific gene.
    kb: Number of kilobases upstream to fetch.
    """
    params = {"kb": kb}
    return await call_genome_backend("GET", f"/api/genome/{id}/promoter/{gene_id}", params=params)

@register_agent_tool
@tool(args_schema=BatchSequencesInput)
async def get_batch_sequences(id: int, gene_ids: List[str], type: str = "genomic") -> Dict[str, Any]:
    """
    Expert Tool: Fetch sequences for multiple genes in one call.
    type: "genomic", "cds", or "protein".
    """
    params = {"type": type}
    return await call_genome_backend("POST", f"/api/genome/{id}/batch-sequences", params=params, json_data=gene_ids)

@register_agent_tool
@tool(args_schema=InvestigateRegionInput)
async def investigate_region(genome_id: int, chrom: str, start: int, end: int, limit: int = 50) -> Dict[str, Any]:
    """
    Expert Tool: Return all features in a specific genomic range.
    """
    params = {"genome_id": genome_id, "chrom": chrom, "start": start, "end": end, "limit": limit}
    return await call_genome_backend("GET", "/api/genome/region/investigate", params=params)

@register_agent_tool
@tool(args_schema=GeneListInput)
async def get_genes_list(genome_id: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
    """
    Retrieve a paginated list of gene annotations for a given genome.

    Requires `genome_id` (must be obtained from `list_genome_files` first).
    Supports pagination via `page` and `limit`.

    Returns:
    - total: total number of genes
    - page, limit: pagination info
    - items: list of genes, each containing:
        - gene_id, name
        - chromosome, start, end, strand
        - description, status
        - id (gene record id), genome_id
    """
    payload = {"genome_id": genome_id, "page": page, "limit": limit}
    return await call_genome_backend("POST", "/api/genome/get-genes", json_data=payload)

@register_agent_tool
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
    Search for genes using flexible filters such as keyword, exact gene ID, chromosome, or genomic coordinates.

    Use this tool when the user wants to find specific genes (by name, ID, or region).
    Prefer providing `genome_id` (from `list_genome_files`) to narrow results.

    Supports:
    - keyword: partial match on gene name/description
    - gene_id_exact: exact gene ID lookup
    - chromosome + start/end: region-based search

    Returns:
    - total, page, limit
    - items: list of matching genes with fields such as:
        gene_id, name, chromosome, start, end, strand,
        description, id, genome_id,
        genomic_sequence, cds_sequence, protein_sequence (if available)
    """
    # Drop None values to keep the payload clean
    payload = {
        k: v for k, v in {
            "genome_id": genome_id, "keyword": keyword, "chromosome": chromosome,
            "gene_id_exact": gene_id_exact, "start": start, "end": end,
            "page": page, "limit": limit
        }.items() if v is not None
    }
    return await call_genome_backend("POST", "/api/genome/search", json_data=payload)

@register_agent_tool
@tool(args_schema=RegionSequenceInput)
async def get_region_sequence(genome_id: int, chrom: str, start: int, end: int) -> Dict[str, Any]:
    """
    Retrieve the raw genomic sequence for a specific chromosomal region.
    Note: 'file_id' from OpenAPI is mapped to 'genome_id'.
    """
    params = {"file_id": genome_id, "chrom": chrom, "start": start, "end": end}
    return await call_genome_backend("GET", "/api/genome/region/sequence", params=params)

@register_agent_tool
@tool
async def get_gene_detail(gene_id: str, genome_id: int) -> Dict[str, Any]:
    """
    Retrieve detailed information for a single gene, including coordinates and sequences.

    Use this tool when the user requests full details or sequences of a specific gene.
    Requires BOTH:
    - gene_id: exact gene identifier (e.g., Soffi...)
    - genome_id: obtained from `list_genome_files`

    Returns a gene object with fields such as:
    - gene_id, name, chromosome, start, end, strand
    - description, status, id, genome_id
    - genomic_sequence, cds_sequence, protein_sequence, upstream_flank (if available)
    """
    params = {"genome_id": genome_id}
    return await call_genome_backend("GET", f"/api/genome/detail/{gene_id}", params=params)

# @tool
# async def get_sequence_raw(genome_id: int, gene_id: str, type: str = "genomic") -> Dict[str, Any]:
#     """
#     Quickly retrieve ONLY the raw string sequence for a gene.
#     Requires 'genome_id', 'gene_id', and 'type' (must be one of: "genomic", "cds", "protein", "flank").
#     """
#     params = {"genome_id": genome_id, "gene_id": gene_id, "type": type}
#     return await call_genome_backend("GET", "/api/genome/sequence", params=params)

@register_agent_tool
@tool(args_schema=BlastInput)
async def run_blast(genome_id: int, sequence: str, evalue: float = 1e-5) -> Dict[str, Any]:
    """
    Run a BLAST alignment of a query sequence against a selected genome database.

    Use this tool when the user provides a DNA/protein sequence and wants to find similar regions.
    Requires:
    - genome_id: target genome database (must be obtained from `list_genome_files`)
    - sequence: query sequence (DNA or protein)

    Optional:
    - evalue: significance threshold (default 1e-5)

    Returns BLAST results including hits, alignments, scores, e-values, and matched regions.
    """
    payload = {"genome_id": genome_id, "sequence": sequence, "evalue": evalue}
    return await call_genome_backend("POST", "/api/blast/run", json_data=payload)

# @tool(args_schema=SyntenyInput)
# async def run_synteny_analysis(
#     genome_a_id: int, genome_b_id: int,
#     start_a: Optional[int] = None, end_a: Optional[int] = None,
#     start_b: Optional[int] = None, end_b: Optional[int] = None,
#     check_quality: bool = True,
# ) -> Dict[str, Any]:
#     """
#     Perform synteny block analysis to compare the structure of two different genomes.
#     Requires BOTH 'genome_a_id' and 'genome_b_id'. Optional coordinates can focus the analysis on specific regions.
#     """
#     payload = {
#         k: v for k, v in {
#             "genome_a_id": genome_a_id, "genome_b_id": genome_b_id,
#             "start_a": start_a, "end_a": end_a, "start_b": start_b, "end_b": end_b,
#             "check_quality": check_quality
#         }.items() if v is not None
#     }
#     return await call_genome_backend("POST", "/api/synteny/analyze", json_data=payload)

@register_agent_tool
@tool(args_schema=PaginationInput)
async def list_synteny_tasks(page: int = 1, size: int = 50) -> Dict[str, Any]:
    """
    List all synteny analysis tasks.
    """
    params = {"page": page, "size": size}
    return await call_genome_backend("GET", "/api/synteny", params=params)

@register_agent_tool
@tool
async def run_synteny_analysis(genome_a_id: int, genome_b_id: int, check_quality: bool = True) -> Dict[str, Any]:
    """
    Run synteny analysis between two genomes.
    """
    payload = {"genome_a_id": genome_a_id, "genome_b_id": genome_b_id, "check_quality": check_quality}
    return await call_genome_backend("POST", "/api/synteny/analyze", json_data=payload)

@register_agent_tool
@tool(args_schema=SyntenyHaplotypeInput)
async def run_haplotype_analysis(
    genome_id: int,
    haplotype_set_query: str,
    haplotype_set_subject: str,
    homologous_group: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run synteny/haplotype analysis between two haplotype sets within a genome.
    Use this tool when the user wants to compare genomic regions, detect collinearity,
    or analyze conserved gene order between haplotypes.

    Requires:
    - genome_id: obtained from `list_genome_files`
    - haplotype_set_query: query haplotype set
    - haplotype_set_subject: subject haplotype set

    Optional:
    - homologous_group: restrict analysis to a specific homologous group

    Returns:
    - job_name
    - result_path (.collinearity file for downstream analysis)
    - query_haplotype, subject_haplotype
    - homologous_group (if provided)
    """
    payload = {
        "genome_id": genome_id, 
        "haplotype_set_query": haplotype_set_query,
        "haplotype_set_subject": haplotype_set_subject,
        "homologous_group": homologous_group
    }
    return await call_genome_backend("POST", "/api/synteny/analyze_haplotype", json_data=payload)

@register_agent_tool
@tool
async def get_synteny_status(task_id: int) -> Dict[str, Any]:
    """
    Get status of a synteny analysis task.
    """
    return await call_genome_backend("GET", f"/api/synteny/{task_id}")

@register_agent_tool
@tool(args_schema=PaginationInput)
async def list_crispor_tasks(page: int = 1, size: int = 50) -> Dict[str, Any]:
    """
    List all CRISPOR design tasks.
    """
    params = {"page": page, "size": size}
    return await call_genome_backend("GET", "/api/crispor", params=params)

@register_agent_tool
@tool
async def run_crispor(genome_id: int, gene_id: Optional[str] = None, sequence: Optional[str] = None) -> Dict[str, Any]:
    """
    Design CRISPR gRNA candidates and evaluate off-target effects using CRISPOR.

    Use this tool when the user wants to design guide RNAs for a gene or sequence.
    Requires:
    - genome_id: obtained from `list_genome_files`
    - ONE of:
        - gene_id: to design guides for a known gene (use `search_genes_full` or `get_gene_detail` first)
        - sequence: raw DNA sequence

    Returns:
    - guides_found
    - top_guides: list of candidate gRNAs with:
        sequence, PAM, location, GC content,
        efficiency (Doench score), specificity (CFD score),
        off-target count, and PCR primers (if available)
    """
    # Note: OpenAPI spec says POST, but parameters are 'query' (in)
    params = {k: v for k, v in {"genome_id": genome_id, "gene_id": gene_id, "sequence": sequence}.items() if v is not None}
    return await call_genome_backend("POST", "/api/crispor", params=params)

@register_agent_tool
@tool(args_schema=PaginationInput)
async def list_primer_tasks(page: int = 1, size: int = 50) -> Dict[str, Any]:
    """
    List all primer design tasks.
    """
    params = {"page": page, "size": size}
    return await call_genome_backend("GET", "/api/primer", params=params)

@register_agent_tool
@tool
async def get_primer_task(task_id: int) -> Dict[str, Any]:
    """
    Get details and results of a primer design task.
    """
    return await call_genome_backend("GET", f"/api/primer/{task_id}")

@register_agent_tool
@tool(args_schema=PrimerDesignInput)
async def design_polyploid_primer(
    genome_id: int, query: str, primer_num_return: int = 20,
    primer_product_size_range: str = "100-400", primer_opt_size: int = 20,
    primer_min_size: int = 18, primer_max_size: int = 24,
    primer_opt_tm: float = 60, primer_min_tm: float = 52, primer_max_tm: float = 68,
    primer_min_gc: float = 20, primer_max_gc: float = 80, primer_opt_gc_percent: float = 50,
) -> Dict[str, Any]:
    """
    Design PCR primers optimized for polyploid genomes, ensuring specificity across homologous regions.

    Use this tool when the user wants to design primers for amplification (PCR/qPCR),
    especially in complex genomes with multiple homologs (e.g., polyploid species).

    Requires:
    - genome_id: genome reference (must be obtained from `list_genome_files`)
    - query: target DNA sequence or region

    Optional parameters control primer design constraints (size, Tm, GC content, product size).

    Returns:
    - mode (e.g., Polyploid)
    - homologs_used, consensus sequence preview
    - primers: list of primer pairs with:
        left/right sequences, predicted amplicon size,
        and specificity mode (e.g., single-band)
    """
    payload = {
        "genome_id": genome_id, "query": query, "primer_num_return": primer_num_return,
        "primer_product_size_range": primer_product_size_range, "primer_opt_size": primer_opt_size,
        "primer_min_size": primer_min_size, "primer_max_size": primer_max_size,
        "primer_opt_tm": primer_opt_tm, "primer_min_tm": primer_min_tm, "primer_max_tm": primer_max_tm,
        "primer_min_gc": primer_min_gc, "primer_max_gc": primer_max_gc, "primer_opt_gc_percent": primer_opt_gc_percent
    }
    return await call_genome_backend("POST", "/api/primer/design_polyploid", json_data=payload)