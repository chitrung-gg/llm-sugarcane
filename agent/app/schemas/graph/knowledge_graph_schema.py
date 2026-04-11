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


class KnowledgeGraphComponents(BaseModel):
    is_domain_relevant: bool = Field(
        description="True ONLY if the text is specifically about plant biology, sugarcane, genomics, or related agricultural sciences. False if it is about human medicine, irrelevant news, etc."
    )
    nodes: List[KnowledgeGraphNode] = Field(description="List of entities extracted from the text.")
    relationships: List[KnowledgeGraphRelationship] = Field(description="List of relationships between entities.")
