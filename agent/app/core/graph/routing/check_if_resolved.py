from langgraph.graph import END
from loguru import logger

from app.core.graph.state.agent_state import AgentState


def check_if_resolved(state: AgentState):
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    
    # Circuit Breaker: ALWAYS have a hard stop so you don't burn tokens
    if iteration_count >= max_iterations:
        logger.error("🛑 Max iterations reached. Forcing END.")
        return END
        
    is_complete = state.get("is_complete", False)
    if is_complete:
        return END
    else:
        logger.warning(f"🔄 Answer incomplete. Looping back to router (Iteration {iteration_count + 1})")
        return "router"