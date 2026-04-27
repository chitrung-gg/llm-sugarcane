from enum import StrEnum


class IngestionConfidenceTier(StrEnum):
    CURATED = "curated"
    INFERRED = "inferred"
    PROVISIONAL = "provisional"


class IngestionSourceType(StrEnum):
    # --- System & Reference Sources (Public/Global) ---
    SYSTEM_REFERENCE_GENOME = "system_reference_genome"
    SYSTEM_CURATED_DOCUMENT = "system_curated_document"
    SYSTEM_DATABASE = "system_database"
    
    # --- User & Private Sources (Scoped to User/Project) ---
    USER_PRIVATE_GENOME = "user_private_genome"
    USER_PRIVATE_DOCUMENT = "user_private_document"
    USER_PRIVATE_DATABASE = "user_private_database"
    
    # --- Agentic & Temporary Sources ---
    AGENT_WEB_SEARCH = "agent_web_search"
    
    # --- Agentic NCBI APIs ---
    NCBI_LITERATURE = "ncbi_literature"     # PubMed Abstracts
    NCBI_GENE = "ncbi_gene"                 # Gene Metadata & Ontology
    NCBI_GENOME = "ncbi_genome"             # Genome Assembly Stats
    NCBI_BIOPROJECT = "ncbi_bioproject"     # Project Background/Goals
    NCBI_BIOSAMPLE = "ncbi_biosample"       # Tissue/Environment samples
    NCBI_TAXONOMY = "ncbi_taxonomy"         # Taxonomic resolution