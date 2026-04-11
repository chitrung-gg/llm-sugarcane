from enum import StrEnum
import time
from typing import List, Literal, cast
from loguru import logger
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.types import Command
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from pydantic import BaseModel, Field

from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState, WebResult

class OptimizedSearchQuery(BaseModel):
    """Schema to force the LLM to output a clean search string."""
    search_query: str = Field(
        description="A standalone, keyword-rich search query optimized for search engines. Omit conversational filler."
    )
    
def make_web_search_node(
    searx_wrapper: SearxSearchWrapper,
    llm_service: LLMService
):
    """Factory to create the web search node with injected dependency."""

    async def web_search(state: AgentState) -> Command[
        Literal[AgentGraphNode.SYNTHESIZER]
    ]:
        logger.debug("--- 🌐 TRIGGERING SEARXNG WEB SEARCH ---")
        start_time = time.time()

        original_query = state["query"]

        # 1. Query Optimization
        system_prompt = f"""
            You are a Search Query Optimizer. The user is asking a conversational question.
            Convert the user's latest query into a standalone, keyword-dense search engine query.
            
            CONVERSATION SUMMARY:
            {state.get("summary", "No prior context.")}
            
            RULES:
            - DO NOT use conversational filler (remove "I want to know more about", "What is").
            - Resolve pronouns ("it", "this gene") using the summary.
            - Output ONLY the optimized search string.
        """

        messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
        if state["messages"]:
            messages.extend(state["messages"])
        messages.append(HumanMessage(content=f"Latest Query: {original_query}"))

        try:
            # Use your fastest/cheapest model here (e.g., secondary or tertiary)
            rewriter_llm = llm_service.get_quaternary_model().with_structured_output(OptimizedSearchQuery)
            rewritten_result = await rewriter_llm.ainvoke(messages)
            optimized_query = OptimizedSearchQuery.model_validate(rewritten_result).search_query
            logger.info(f"[Web Search] 🪄 Optimized query: '{optimized_query}' (Original: '{original_query}')")
        except Exception as e:
            logger.warning(f"[Web Search] Query optimization failed: {e}. Falling back to original query.")
            optimized_query = original_query
        
        # 2. Execute search
        new_web_results = []

        try:
            raw_results = searx_wrapper.results(optimized_query, num_results=5)
            
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

        return Command(
            goto=AgentGraphNode.SYNTHESIZER,
            update={"web_results": new_web_results}
        )
    
    return web_search