from pydantic import BaseModel


class AgentResponse(BaseModel):
    answer: str
    execution_time: float