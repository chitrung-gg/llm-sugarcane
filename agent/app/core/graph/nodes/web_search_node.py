import time
from typing import Literal
from loguru import logger
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.types import Command

from app.core.graph.state.agent_state import AgentState, WebResult

after_web_search_node = Literal["synthesizer"]

def make_web_search_node(searx_wrapper: SearxSearchWrapper):
    """Factory to create the web search node with injected dependency."""

    async def web_search(state: AgentState) -> Command[after_web_search_node]:
        logger.debug("--- 🌐 TRIGGERING SEARXNG WEB SEARCH ---")

        query = state["query"]
        start_time = time.time()
        
        new_web_results = []

        try:
            # .results() gives us structured JSON instead of a raw string!
            raw_results = searx_wrapper.results(query, num_results=5)
            
            for res in raw_results:
                web_item = WebResult(
                    snippet=res.get("snippet", "No snippet available"),
                    title=res.get("title", "No Title"),
                    link=res.get("link", ""),
                    engines=res.get("engines", []),
                    category=res.get("category", "general")
                )
                new_web_results.append(web_item)
                
        except Exception as e:
            logger.error("SearXNG search failed: {error}", error=str(e))
            # Inject an error result so the Synthesizer knows the search failed
            new_web_results.append(
                WebResult(
                    snippet=f"Web search failed due to an error: {str(e)}",
                    title="Search Error",
                    link="",
                    engines=[],
                    category="error"
                )
            )
        
        execution_time = int((time.time() - start_time) * 1000)
        logger.debug(
            "[Web Search] ✅ Completed in {execution_time} ms | Found {count} items", 
            execution_time=execution_time, count=len(new_web_results)
        )

        # Because web_results uses operator.add, returning a list appends it to state
        return Command(
            goto="synthesizer",
            update={"web_results": new_web_results}
        )
    
    return web_search