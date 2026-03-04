from langgraph.graph import END

from app.core.graph.state.agent_state import AgentState


def check_if_resolved(state: AgentState) -> str:
    if state.get("is_complete"):
        return END
    # If not, return to router node to plan to continue searching
    return "router"