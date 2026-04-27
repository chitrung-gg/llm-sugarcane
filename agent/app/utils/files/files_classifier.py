from pathlib import Path

from app.common.constants import (
    COMPRESSED_SUFFIXES, 
    GENOMIC_EXTENSIONS, 
    KNOWLEDGE_EXTENSIONS,
    SEQUENCE_BASE,
    ANNOTATION_BASE
)


def extract_full_extension(filename: str) -> str:
    """
    Safely extracts double-extensions like '.fasta.gz' or '.gff3.gz'.
    Otherwise, returns the single extension like '.pdf'.
    """
    path = Path(filename)
    suffixes = path.suffixes
    
    if not suffixes:
        return ""
        
    # If the last suffix is a compression format and there is a base format before it
    if len(suffixes) >= 2 and suffixes[-1].lower() in COMPRESSED_SUFFIXES:
        return "".join(suffixes[-2:]).lower()
        
    return suffixes[-1].lower()

def is_genomic_file(filename: str) -> bool:
    """Returns True if the file is a recognized bioinformatics format."""
    ext = extract_full_extension(filename)
    return ext in GENOMIC_EXTENSIONS

def is_knowledge_file(filename: str) -> bool:
    """Returns True if the file is a document/image meant for Docling/RAG."""
    ext = extract_full_extension(filename)
    return ext in KNOWLEDGE_EXTENSIONS

def get_genomic_file_type(filename: str) -> str:
    """
    Maps a filename extension to a semantic genomic type for the ETL pipeline.
    Uses defined constants for type mapping.
    """
    ext = extract_full_extension(filename).lower()
    
    # Check for base extension before potential .gz
    base_ext = ext
    for suffix in COMPRESSED_SUFFIXES:
        if ext.endswith(suffix):
            base_ext = ext[:-len(suffix)]
            break

    if base_ext in SEQUENCE_BASE:
        # Heuristic for sub-types
        fn_lower = filename.lower()
        if "cds" in fn_lower: return "cds"
        if "pep" in fn_lower or "protein" in fn_lower: return "protein"
        return "genome"
    
    if base_ext in ANNOTATION_BASE:
        return "gff3"
    
    return "unknown"
