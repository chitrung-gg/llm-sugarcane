import time

from langchain_community.utilities.searx_search import SearxSearchWrapper
from loguru import logger

from app.core.graph.state.agent_state import AgentState, ToolResult

def make_web_search_node(searx_wrapper: SearxSearchWrapper):
    """Factory to create the web search node with injected dependency."""

    async def web_search(state: AgentState) -> dict:
        logger.debug("--- 🌐 TRIGGERING SEARXNG WEB SEARCH ---")

        query = state["query"]
        start_time = time.time()

        try:
            raw_results = searx_wrapper.run(query)
            status = "success"
        except Exception as e:
            logger.error(f"SearXNG search failed: {e}")
            raw_results = f"Web search failed due to an error: {str(e)}"
            status = "error"
        
        execution_time = int((time.time() - start_time) * 1000)

        # Package into custom schema
        search_result = ToolResult(
            tool_name="searxng_web_search",
            status=status,
            output=raw_results,
            execution_time_ms=execution_time
        )

        # Because tool_results uses operator.add, returning a list appends it to state
        return {
            "tool_results": [search_result]
        }
    
    return web_search
