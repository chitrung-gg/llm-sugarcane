import uuid
from typing import List
from pydantic import BaseModel, Field

class PruningOutput(BaseModel):
    """
    Schema for the Biological Context Pruning Specialist.
    Used to filter irrelevant files from the context window.
    """
    scratchpad: str = Field(description="Step-by-step reasoning on biological relevance.")
    relevant_file_ids: List[uuid.UUID] = Field(description="List of dataset/file IDs that are strictly necessary for the query.")
    reasoning: str = Field(description="One-sentence summary of the selection logic.")
