from typing import Literal

from langgraph.graph import END
from loguru import logger

from app.core.graph.state.agent_state import AgentState

after_if_resolved_node = Literal["router", "__end__"]       # END in langgraph.graph

def check_if_resolved(state: AgentState) -> after_if_resolved_node:
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3) 
    
    logger.debug(
        "🔄 Checking resolution. Loop: {count}/{max}", 
        count=iteration_count, max=max_iterations
    )

    # HARD STOP - CIRCUIT BREAKER
    if iteration_count >= max_iterations:
        logger.error("🛑 Max iterations reached! Forcing the graph to END.")
        return "__end__"
        
    # STANDARD CHECK
    is_complete = state.get("is_complete", False)
    if is_complete:
        logger.debug("✅ Answer complete. Ending graph.")
        return "__end__"
    else:
        logger.warning("⚠️ Answer incomplete. Sending back to Router.")
        return "router"