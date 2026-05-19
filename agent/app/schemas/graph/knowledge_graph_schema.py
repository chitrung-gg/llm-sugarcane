import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.common.constants import GraphIngestionAllowedLabels

_ALLOWED_LABELS_STR = ", ".join([f"'{label.value}'" for label in GraphIngestionAllowedLabels])
PREFERRED_RELATIONSHIP_TYPES = [
    # Molecular / Genetic
    "ENCODES",          # Gene -> Protein
    "REGULATES",        # Gene -> Gene/Trait  
    "INHIBITS",         # Protein -> Gene/Pathway
    "ACTIVATES",        # Protein -> Gene/Pathway
    "INTERACTS_WITH",   # Protein <-> Protein
    "MAPPED_TO",        # Gene -> Locus/QTL

    # Expression / Location
    "EXPRESSED_IN",     # Gene -> Tissue
    "LOCATED_IN",       # Gene -> Tissue/Cultivar
    "FOUND_IN",         # Entity -> Cultivar/Sample
    "PRODUCED_BY",      # Metabolite -> Enzyme

    # Disease / Stress
    "RESISTANT_TO",     # Cultivar -> Disease
    "SUSCEPTIBLE_TO",   # Cultivar -> Disease
    "RESPONDS_TO",      # Gene/Cultivar -> Environmental_Stress  
    "HAS_SYMPTOM",      # Disease -> Trait (plant symptom)       
    "CAUSED_BY",        # Disease -> Pathogen/Stress 

    # Trait / Phenotype
    "AFFECTS",          # Gene/Stress -> Trait
    "CONTRIBUTES_TO",   # Gene -> Trait
    "CONFERS",          # Gene/Allele -> Resistance/Trait        

    # General
    "ASSOCIATED_WITH",  # fallback generic
]
_PREFERRED_REL_STR = ", ".join([f"'{r}'" 
for r in PREFERRED_RELATIONSHIP_TYPES])

class KnowledgeGraphNode(BaseModel):
    name: str = Field(
        description="The primary name of the entity."
    )
    label: GraphIngestionAllowedLabels = Field(
        description=f"Strictly one of: {_ALLOWED_LABELS_STR}"
    )
    description: Optional[str] = Field(
        default=None, 
        description="A brief description or definition of the entity found in the text."
    )
    aliases: Optional[List[str]] = Field(
        default_factory=list, 
        description="Any alternative names, acronyms, or synonyms for this entity mentioned in the text."
    )


class KnowledgeGraphRelationship(BaseModel):
    source_name: str = Field(description="The exact name of the source node.")
    target_name: str = Field(description="The exact name of the target node.")
    type: str = Field(
        description=(
            f"Relationship type in UPPER_SNAKE_CASE. "
            f"STRONGLY PREFER these established types: {_PREFERRED_REL_STR}. "
            f"Only invent a NEW type if none of the above accurately captures the relationship. "
            f"Do NOT create synonyms of existing types (e.g., use 'RESISTANT_TO', not 'SHOWS_RESISTANCE_TO')."
        )
      )
    evidence: str = Field(
        description="The exact short snippet of text that proves this relationship exists."
    )
    context: Optional[str] = Field(
        default=None, 
        description="Any specific conditions (e.g., 'under drought stress', 'in leaf tissue')."
    )
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0). "
                    "0.9-1.0: Explicitly stated scientific fact. "
                    "0.6-0.8: Strongly implied or secondary information. "
                    "0.0-0.5: Speculative, ambiguous, or unverified claim."
    )

    @field_validator("type")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        normalized = v.strip().upper()
        normalized = re.sub(r'[\s\-]+', '_', normalized)
        normalized = re.sub(r'[^A-Z0-9_]', '', normalized)
        normalized = re.sub(r'_+', '_', normalized).strip('_')
        return normalized


class KnowledgeGraphComponents(BaseModel):
    is_domain_relevant: bool = Field(
        description="True ONLY if the text is specifically about plant biology, sugarcane, genomics, or related agricultural sciences. False if it is about human medicine, irrelevant news, etc."
    )
    overall_confidence: float = Field(
        description="Score (0.0 to 1.0) representing the scientific reliability of the ENTIRE text. "
                    "0.8-1.0: Primary literature, official databases (e.g., NCBI), curated genomes. "
                    "0.5-0.7: General web articles, summaries, wikis. "
                    "0.0-0.4: Unknown sources, messy outputs, or incomplete data."
    )
    nodes: List[KnowledgeGraphNode] = Field(description="List of entities extracted from the text.")
    relationships: List[KnowledgeGraphRelationship] = Field(description="List of relationships between entities.")


class BatchKnowledgeGraphComponents(BaseModel):
    results: List[KnowledgeGraphComponents] = Field(
        description="A list of extraction results, one for each provided text chunk in the exact same order."
    )
