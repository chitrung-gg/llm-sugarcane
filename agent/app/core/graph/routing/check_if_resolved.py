from langgraph.graph import END
from loguru import logger

from app.core.graph.state.agent_state import AgentState


def check_if_resolved(state: AgentState):
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3) 
    
    logger.debug(f"🔄 Checking resolution. Loop: {iteration_count}/{max_iterations}")

    # HARD STOP - CIRCUIT BREAKER
    if iteration_count >= max_iterations:
        logger.error("🛑 Max iterations reached! Forcing the graph to END.")
        return END
        
    # STANDARD CHECK
    is_complete = state.get("is_complete", False)
    if is_complete:
        logger.debug("✅ Answer complete. Ending graph.")
        return END
    else:
        logger.warning("⚠️ Answer incomplete. Sending back to Router.")
        return "router"