from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field
import operator

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

class AgentStepPlan(BaseModel):
    """Represents a single deterministic step in the research plan."""
    step_id: int = Field(description="Sequential ID of the step (e.g., 1, 2, 3)")
    description: str = Field(description="What needs to be done.")
    expected_tool: Optional[str] = Field(description="The specific tool required for this step.")
    
    # --- Replanning ---
    status: Literal["pending", "running", "completed", "failed"] = Field(default="pending")
    error_message: Optional[str] = Field(
        default=None, 
        description="If the step fails, the Executor will write the exact tool error/traceback here."
    )
    retry_count: int = Field(default=0, description="Tracks how many times this step has been retried.")

class AgentStepObservation(BaseModel):
    """Stores structured data extracted during a step, making it easy to pass to the next step."""
    step_id: int
    summary: str = Field(description="Human-readable summary of what was found.")
    extracted_data: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Crucial variables (e.g., {'gene_id': 'ROC-123', 's3_uri': 's3://...'})"
    )