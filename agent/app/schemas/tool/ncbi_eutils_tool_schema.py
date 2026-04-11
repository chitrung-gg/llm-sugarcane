from typing import Optional

from pydantic import BaseModel, Field

class PubMedSearchArgs(BaseModel):
    organism: str = Field(description="The scientific name of the plant (e.g., 'Saccharum').")
    primary_concept: str = Field(description="The ONE main trait or disease (e.g., 'sugar content', 'smut'). Keep it to 1-2 words max.")
    secondary_concept: Optional[str] = Field(default=None, description="ONE optional related concept (e.g., 'CRISPR', 'resistance'). Leave blank for a broader search.")

class GeneSearchArgs(BaseModel):
    organism: str = Field(description="The scientific organism name (e.g., 'Saccharum', 'Sorghum bicolor').")
    gene_symbol: str = Field(description="The strict, short scientific gene symbol/acronym ONLY (e.g., 'Scmv1', 'SPS', 'SuSy'). Do NOT include full names or traits.")

class GenomeSearchArgs(BaseModel):
    organism_or_cultivar: str = Field(description="The organism and cultivar name (e.g., 'Saccharum r570'). Best practice: use the exact TaxID if known.")

class BioProjectSearchArgs(BaseModel):
    query: str = Field(
        description=(
            "The search term to find the project's background story and goals. "
            "BEST: Provide the exact BioProject Accession (e.g., 'PRJNA945843'). "
            "ALTERNATE: Provide the organism and cultivar (e.g., 'Saccharum R570'). "
            "Do NOT use long conversational sentences."
        )
    )

class BioSampleSearchArgs(BaseModel):
    query: str = Field(
        description=(
            "The search term to find physical tissue, developmental stage, or geographic metadata. "
            "BEST: Provide the exact BioSample Accession (e.g., 'SAMN33824311'). "
            "ALTERNATE: Provide the organism and cultivar (e.g., 'Saccharum R570'). "
            "Do NOT include the word 'BioSample' in the query string itself."
        )
    )

class TaxonomySearchArgs(BaseModel):
    query: str = Field(
        description="The common name, messy scientific name, or hybrid name of the organism (e.g., 'sugarcane', 'Saccharum officinarum x spontaneum')."
    )

class NucleotideSearchArgs(BaseModel):
    accession: str = Field(
        description="The EXACT Nucleotide Accession ID (e.g., 'NM_001166461.1'). Do NOT pass gene symbols or organism names here."
    )
    start_pos: Optional[int] = Field(
        default=1, 
        description="The starting base pair position. Default is 1."
    )
    stop_pos: Optional[int] = Field(
        default=5000, 
        description="The ending base pair position. MAXIMUM allowed is 10000 to prevent context overflow."
    )