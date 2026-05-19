from pydantic import BaseModel


class KnowledgeGraphInput(BaseModel):
    query: str
    top_k: int = 5