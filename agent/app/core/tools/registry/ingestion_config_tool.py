from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.vector_store.vector_store import VectorStoreType


class IngestionConfidenceTier(StrEnum):
    CURATED = "curated"
    INFERRED = "inferred"
    PROVISIONAL = "provisional"


class IngestionConfig(BaseModel):
    vector_store_type: VectorStoreType = Field(...)
    source_type_label: str = Field(...)
    
    ingestion_confidence_tier: IngestionConfidenceTier = Field(
        description="The scientific reliability tier: 'curated' (papers/official), 'inferred' (API/LLM), or 'provisional' (web searches)."
    )

    skip_relevance_check: bool = Field(default=False)

