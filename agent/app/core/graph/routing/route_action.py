from typing import List, Literal

from loguru import logger
from pydantic import BaseModel, Field

from app.core.graph.state.agent_state import AgentState


def route_action(state: AgentState):
    # Safely extract the intent from the state
    intent = state.get("intent")
    
    # 🚦 DEBUG: This will prove if LangGraph correctly merged the state
    logger.debug(f"🚦 [Conditional Edge] State Intent received: '{intent}'")
    
    if intent == "rag_only":
        return "rag_execution"
    elif intent == "tool_only":  
        return "tool_execution"
    elif intent == "web_search": 
        return "web_search"
    elif intent == "all":
        # Return list of nodes so that LangGraph can run request parallel. 
        return ["rag_execution", "tool_execution", "web_search"] 
    else:
        # Fallback for "unclear" or any unexpected intent
        return "synthesizer"
    
class RouteDecision(BaseModel):
    intent: Literal["rag_only", "tool_only", "all", "unclear", "web_search"] = Field(
        description="Determine the routing intent based on the user query. "
                    "Use 'web_search' for fetching the latest news, external databases, or information not found in vector stores."
    )
    required_tools: List[str] = Field(
        description="List of required tool names (e.g., ['blast', 'synteny']). Leave empty if no tools are needed."
    )