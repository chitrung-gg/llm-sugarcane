from pydantic import BaseModel, Field

class SynthesizerOutput(BaseModel):
    answer: str = Field(
        description="The detailed response to the user. If a background process was triggered (like indexing), confirm it to the user."
    )
    is_complete: bool = Field(
        description="Set to True if you fully answered the query OR if you have triggered the requested action (like retriggering a pipeline). Set to False ONLY if a tool failed and you need to try a DIFFERENT approach."
    )
    missing_info: str = Field(
        description="If is_complete is False, explicitly state what specific information is missing."
    )
