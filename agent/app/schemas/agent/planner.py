from typing import List, Optional
from pydantic import BaseModel, Field
from app.core.graph.state.planner_state import AgentStepPlan

class PlanOutput(BaseModel):
    scratchpad: str = Field(description="Reasoning on validity, logic, and file availability.")
    direct_response: Optional[str] = Field(None, description="If no steps are needed, write the direct, helpful, conversational answer to the user here.")
    estimated_steps: int = Field(description="The total number of steps in the proposed plan.")
    steps: List[AgentStepPlan] = Field(default_factory=list, description="The sequential steps to execute the research plan. Maximum 5 steps.")
