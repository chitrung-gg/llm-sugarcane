from typing import List, Literal

from pydantic import BaseModel, Field

from app.core.graph.state.agent_state import AgentState


def route_action(state: AgentState):
    # Safely extract the intent from the state
    intent = state.get("intent")
    
    # 🚦 DEBUG: This will prove if LangGraph correctly merged the state
    print(f"🚦 [Conditional Edge] State Intent received: '{intent}'")
    
    if intent == "rag_only":
        return "rag_execution"
    elif intent == "tools_only":
        return "tool_execution"
    elif intent == "both":
        # Return list of nodes so that LangGraph can run request parallel. 
        return ["rag_execution", "tool_execution"] 
    else:
        return "synthesizer"
    
class RouteDecision(BaseModel):
    intent: Literal["rag_only", "tool_only", "both", "unclear"] = Field(
        description="Determine the routing intent based on the user query."
    )
    required_tools: List[str] = Field(
        description="List of required tool names (e.g., ['blast', 'synteny']). Leave empty if no tools are needed."
    )
