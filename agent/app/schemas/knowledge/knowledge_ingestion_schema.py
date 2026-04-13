from enum import StrEnum


class IngestionConfidenceTier(StrEnum):
    CURATED = "curated"
    INFERRED = "inferred"
    PROVISIONAL = "provisional"


class IngestionSourceType(StrEnum):
    # --- Manual & Local Sources ---
    CURATED_DOCUMENT = "curated_document"   # Uploaded PDFs/Files
    LOCAL_DATABASE = "local_database"       # Internal Postgres genome syncs
    
    # --- Agentic Web Sources ---
    AGENT_WEB_SEARCH = "agent_web_search"   # SearXNG / General Web
    
    # --- Agentic NCBI APIs ---
    NCBI_LITERATURE = "ncbi_literature"     # PubMed Abstracts
    NCBI_GENE = "ncbi_gene"                 # Gene Metadata & Ontology
    NCBI_GENOME = "ncbi_genome"             # Genome Assembly Stats
    NCBI_BIOPROJECT = "ncbi_bioproject"     # Project Background/Goals
    NCBI_BIOSAMPLE = "ncbi_biosample"       # Tissue/Environment samples
    NCBI_TAXONOMY = "ncbi_taxonomy"         # Taxonomic resolution