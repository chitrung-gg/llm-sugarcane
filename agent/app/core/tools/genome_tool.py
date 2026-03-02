from typing import Optional, List, Dict, Any
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.services.tools.genome_http_client import call_backend
from app.schemas.tool.genome_tool_schema import BlastInput, GeneListInput, GeneSearchInput, PrimerDesignInput, SyntenyInput

@tool
def list_genome_files() -> Dict[str, Any]:
    """
    List available genome files.

    Returns:
        Dict[str, Any]: Raw JSON response containing genome file metadata.
    """
    return call_backend(method="GET", endpoint="/api/genomes/files")


@tool
def get_region_sequence(
    file_id: int,
    chrom: str,
    start: int,
    end: int,
) -> Dict[str, Any]:
    """
    Retrieve genomic sequence for a specific region.

    Args:
        file_id (int): Genome file identifier.
        chrom (str): Chromosome name.
        start (int): Start position (1-based).
        end (int): End position (inclusive).

    Returns:
        Dict[str, Any]: Sequence data for the requested region.
    """
    ...

@tool
def get_region_annotation(
    file_id: int,
    chrom: str,
    start: int,
    end: int,
) -> Dict[str, Any]:
    """
    Retrieve gene annotations within a genomic region.

    Args:
        file_id (int): Genome file identifier.
        chrom (str): Chromosome name.
        start (int): Start coordinate.
        end (int): End coordinate.

    Returns:
        Dict[str, Any]: Annotation data for the specified region.
    """
    ...

@tool
def get_all_genomes() -> List[Dict[str, Any]]:
    """
    Retrieve all genomes for dropdown selection.

    Returns:
        List[Dict[str, Any]]: List of genomes with metadata.
    """
    ...

@tool(args_schema=GeneListInput)
def get_genes_list(
    genome_id: int,
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Retrieve paginated gene metadata list.

    Args:
        genome_id (int): Genome identifier.
        page (int): Page number.
        limit (int): Number of records per page.

    Returns:
        Dict[str, Any]: Paginated gene metadata response.
    """
    ...


@tool(args_schema=GeneSearchInput)
def search_genes_full(
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
    Perform advanced gene search.

    Supports keyword, coordinate, chromosome, and exact gene filtering.

    Returns:
        Dict[str, Any]: Paginated gene detail response.
    """
    ...

@tool
def get_gene_detail(
    gene_id: str,
    genome_id: int,
) -> Dict[str, Any]:
    """
    Retrieve detailed information for a gene.

    Args:
        gene_id (str): Gene identifier (e.g., SoffiXsponR570...).
        genome_id (int): Genome identifier.

    Returns:
        Dict[str, Any]: Detailed gene information including sequences.
    """
    ...

@tool
def get_sequence_raw(
    genome_id: int,
    gene_id: str,
    type: str = "genomic",
) -> Dict[str, Any]:
    """
    Retrieve raw sequence for a gene.

    Args:
        genome_id (int): Genome identifier.
        gene_id (str): Gene ID.
        type (str): Sequence type. Options:
            - genomic
            - cds
            - protein
            - flank

    Returns:
        Dict[str, Any]: Raw sequence data.
    """
    ...


@tool(args_schema=BlastInput)
def run_blast(
    file_id: int,
    sequence: str,
    program: str = "blastn",
    evalue: float = 1e-5,
) -> Dict[str, Any]:
    """
    Run BLAST alignment.

    Args:
        file_id (int): Genome file ID.
        sequence (str): Query nucleotide/protein sequence.
        program (str): BLAST program (blastn, blastp, etc.).
        evalue (float): E-value cutoff threshold.

    Returns:
        Dict[str, Any]: BLAST results.
    """
    ...

@tool(args_schema=SyntenyInput)
def run_synteny_analysis(
    genome_a_id: int,
    genome_b_id: int,
    start_a: Optional[int] = None,
    end_a: Optional[int] = None,
    start_b: Optional[int] = None,
    end_b: Optional[int] = None,
    check_quality: bool = True,
) -> Dict[str, Any]:
    """
    Perform synteny analysis between two genomes.

    Returns:
        Dict[str, Any]: Synteny blocks and analysis results.
    """
    ...

@tool
def run_crispor(
    genome_id: int,
    gene_id: Optional[str] = None,
    sequence: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run CRISPOR gRNA design and off-target analysis.

    Args:
        genome_id (int): Genome identifier.
        gene_id (Optional[str]): Target gene ID.
        sequence (Optional[str]): Direct input sequence.

    Returns:
        Dict[str, Any]: gRNA candidates and off-target results.
    """
    ...

@tool(args_schema=PrimerDesignInput)
def design_polyploid_primer(
    file_id: int,
    query: str,
    primer_num_return: int = 20,
    primer_product_size_range: str = "100-400",
    primer_opt_size: int = 20,
    primer_min_size: int = 18,
    primer_max_size: int = 24,
    primer_opt_tm: float = 60,
    primer_min_tm: float = 52,
    primer_max_tm: float = 68,
    primer_min_gc: float = 20,
    primer_max_gc: float = 80,
    primer_opt_gc_percent: float = 50,
) -> Dict[str, Any]:
    """
    Design primers for polyploid genomes.

    Returns:
        Dict[str, Any]: Primer design result with primer pairs.
    """
    ...
