from typing import List, Optional
from pydantic import BaseModel, Field

class OptimizedSearchQuery(BaseModel):
    """Schema to force the LLM to output a clean search string."""
    search_query: str = Field(
        description="A standalone, keyword-rich search query optimized for search engines. Omit conversational filler."
    )
