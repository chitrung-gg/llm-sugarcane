from typing import List
from pydantic import BaseModel

from app.schemas.tool.tool_execution import ToolExecution


class AgentResponse(BaseModel):
    answer: str
    tool_executions: List[ToolExecution] = []
    execution_time: float