from pydantic import BaseModel, Field

class SummaryOutput(BaseModel):
    """
    Schema for the LLM to output a structured conversation summary.
    """
    new_summary: str = Field(
        description="The comprehensive summary of the conversation to date, gracefully incorporating the new messages."
    )
