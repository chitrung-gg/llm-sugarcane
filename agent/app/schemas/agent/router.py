from typing import List, Optional
from pydantic import BaseModel, Field
from app.common.constants import AgentIntent
from app.schemas.tool.tool_call_request import ToolCallRequest

class RouteDecision(BaseModel):
    reasoning: str = Field(description="Brief explanation of why this route/tool was chosen based on history.")
    intent: AgentIntent = Field(
        description="Determine the routing intent based on the user query. "
                    "Use 'web_search' for fetching the latest news, external databases, or information not found in vector stores."
    )
    required_tools: List[ToolCallRequest] = Field(
        default_factory=list,
        description="List of required tool names (e.g., ['blast', 'synteny']). Leave empty if no tools are needed."
    )
    rag_query: Optional[str] = Field(
        default=None,
        description="Optimized biological keywords for internal document Vector DB search. Keep it concise."
    )
    web_query: Optional[str] = Field(
        default=None,
        description="Optimized search string for external web search (SearxNG). Use academic/genomic identifiers if possible."
    )
