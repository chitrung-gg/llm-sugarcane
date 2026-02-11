from typing import Any, Dict
from pydantic import BaseModel, Field


class ToolExecution(BaseModel):
    tool_name: str = Field(..., description="Name of called tool")
    arguments: Dict[str, Any] = Field(..., description="Arguments passed by LLM")
    result: Any = Field(..., description="Result from tool")
    