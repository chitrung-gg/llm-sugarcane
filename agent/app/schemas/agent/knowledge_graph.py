from typing import List
from pydantic import BaseModel, Field


class GraphPruningResult(BaseModel):
    relevant_paths: List[str] = Field(
        description="A strictly filtered list of exact graph paths that directly help answer the user query. Must be empty if no paths are relevant."
    )