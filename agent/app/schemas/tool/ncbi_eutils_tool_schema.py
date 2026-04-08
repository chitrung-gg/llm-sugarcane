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
    organism_or_cultivar: str = Field(description="The organism and cultivar name (e.g., 'Saccharum r570', 'Sorghum bicolor').")