from typing import List, Literal
from pydantic import BaseModel, Field

class ExecutorOutput(BaseModel):
    """
    Schema for the Executor's inner result.
    The Executor wraps a ReAct agent, but the final output of a step
    is parsed into this structured format for the Plan-and-Execute loop.
    """
    scratchpad: str = Field(description="Step-by-step biological and logical reasoning.")
    status: Literal["SUCCESS", "REQUIRES_CLARIFICATION"] = Field(description="Result status of the specific sub-task.")
    data_extracted: List[str] = Field(description="List of identifiers, accessions, or cultivars found.")
    final_result: str = Field(description="The exact concise answer for this specific step.")
