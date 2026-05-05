from pydantic import BaseModel, Field

class OptimizedRagQuery(BaseModel):
    """Schema to force the LLM to output a clean semantic search string."""
    search_query: str = Field(
        description="A concise, standalone query optimized for semantic search. Maximum 15 words. DO NOT repeat words."
    )
