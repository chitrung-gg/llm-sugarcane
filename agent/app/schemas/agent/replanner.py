from typing import List
from pydantic import BaseModel, Field
from app.core.graph.state.planner_state import AgentStepPlan

class ReplanOutput(BaseModel):
    is_complete: bool = Field(description="True if the user's ORIGINAL query is now fully answered.")
    final_answer: str = Field(description="If complete, write the final, synthesized response to the user here.")
    updated_plan: List[AgentStepPlan] = Field(description="If NOT complete, provide the remaining steps.")
