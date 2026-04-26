from typing import List, Literal, Union

from loguru import logger
from pydantic import BaseModel, Field

from langgraph.types import Command
from app.common.constants import AgentIntent
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.schemas.tool.tool_call_request import ToolCallRequest


def get_routing_destinations(intent: str) -> Union[AgentGraphNode, List[AgentGraphNode]]:
    """Helper function to map LLM intent to graph node destinations."""
    if intent == AgentIntent.RAG_ONLY:
        return AgentGraphNode.RAG
    elif intent == AgentIntent.TOOL_ONLY:  
        return AgentGraphNode.TOOL
    elif intent == AgentIntent.WEB_SEARCH: 
        return AgentGraphNode.WEB_SEARCH
    elif intent == AgentIntent.ALL:
        # Return list of nodes so LangGraph runs them in parallel
        return [
            AgentGraphNode.RAG, 
            AgentGraphNode.TOOL, 
            AgentGraphNode.WEB_SEARCH
        ] 
    elif intent == AgentIntent.DIRECT_ANSWER: 
        return AgentGraphNode.SYNTHESIZER
    else:
        # Fallback for "unclear" or any unexpected intent
        return AgentGraphNode.SYNTHESIZER
    
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