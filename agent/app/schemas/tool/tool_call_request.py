from typing import Any, Dict
from pydantic import BaseModel, Field


# class ToolExecution(BaseModel):
#     tool_name: str = Field(..., description="Name of called tool")
#     arguments: Dict[str, Any] = Field(..., description="Arguments passed by LLM")
#     result: Any = Field(..., description="Result from tool")
    
class ToolCallRequest(BaseModel):
    name: str = Field(description="The exact name of the tool to run")
    args: Dict[str, Any] = Field(description="The JSON arguments required for the tool")