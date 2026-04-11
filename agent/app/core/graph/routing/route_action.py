from typing import List, Literal, Union

from loguru import logger
from pydantic import BaseModel, Field

from langgraph.types import Command
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.schemas.tool.tool_call_request import ToolCallRequest


def get_routing_destinations(intent: str) -> Union[AgentGraphNode, List[AgentGraphNode]]:
    """Helper function to map LLM intent to graph node destinations."""
    if intent == "rag_only":
        return AgentGraphNode.RAG
    elif intent == "tool_only":  
        return AgentGraphNode.TOOL
    elif intent == "web_search": 
        return AgentGraphNode.WEB_SEARCH
    elif intent == "all":
        # Return list of nodes so LangGraph runs them in parallel
        return [
            AgentGraphNode.RAG, 
            AgentGraphNode.TOOL, 
            AgentGraphNode.WEB_SEARCH
        ] 
    elif intent == "direct_answer": 
        return AgentGraphNode.SYNTHESIZER
    else:
        # Fallback for "unclear" or any unexpected intent
        return AgentGraphNode.SYNTHESIZER
    
class RouteDecision(BaseModel):
    reasoning: str = Field(description="Brief explanation of why this route/tool was chosen based on history.")
    intent: Literal["rag_only", "tool_only", "all", "unclear", "web_search", "direct_answer"] = Field(
        description="Determine the routing intent based on the user query. "
                    "Use 'web_search' for fetching the latest news, external databases, or information not found in vector stores."
    )
    required_tools: List[ToolCallRequest] = Field(
        default_factory=list,
        description="List of required tool names (e.g., ['blast', 'synteny']). Leave empty if no tools are needed."
    )