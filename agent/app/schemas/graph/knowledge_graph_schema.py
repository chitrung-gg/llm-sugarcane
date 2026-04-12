from typing import List, Optional

from pydantic import BaseModel, Field

class KnowledgeGraphNode(BaseModel):
    name: str = Field(
        description="The primary name of the entity."
    )
    label: str = Field(
        description="Strictly one of: 'Gene', 'Cultivar', 'Paper', 'Trait', 'Disease', 'Tissue', 'Stress'"
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
        description="The relationship type. MUST be UPPER_SNAKE_CASE (e.g., 'AFFECTS', 'EXPRESSED_IN', 'ASSOCIATED_WITH')."
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
