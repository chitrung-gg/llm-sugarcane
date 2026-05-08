import asyncio
from enum import StrEnum
import time
from typing import List, Literal, cast
from langfuse import observe
from loguru import logger
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.types import Command
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from pydantic import BaseModel, Field

from app.common.constants import ObservationType
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState, WebResult
from app.core.prompts.web_search_prompts import WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT
from app.schemas.agent.web_search import OptimizedSearchQuery
from app.utils.graph.context_utils import get_recent_messages

def make_web_search_node(
    searx_wrapper: SearxSearchWrapper,
    llm_service: LLMService
):
    """Factory to create the web search node with injected dependency."""
    @tracing(observation_type=ObservationType.RETRIEVER)
    async def web_search(state: AgentState) -> Command[
        Literal[AgentGraphNode.SYNTHESIZER]
    ]:
        settings = get_settings()

        logger.debug("--- 🌐 TRIGGERING SEARXNG WEB SEARCH ---")
        start_time = time.time()

        # Check if the Router provided a specific search query
        optimized_query = state.get("web_query")
        
        if not optimized_query:
            # Fallback check for tool calls if web_query is missing
            required_tools = state.get("required_tools", [])
            for tool_call in required_tools:
                if tool_call.name == "web_search" and "query" in tool_call.args:
                    optimized_query = tool_call.args["query"]
                    break

        if optimized_query:
            logger.info(f"[Web Search] 💡 Using pre-optimized query: '{optimized_query}'")
        else:
            original_query = state["query"]
            max_query_length = settings.WEB_SEARCH_MAX_QUERY_LENGTH

            # 1. Query Optimization (Skip if already provided)
            logger.info("[Web Search] No pre-optimized query found. Rewriting...")
            system_prompt = WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT.format(
                conversation_summary=state.get("summary", "No prior context.")
            )

            # Include recent messages for context
            recent_messages = get_recent_messages(state.get("messages", []), n=3)

            messages: List[BaseMessage] = [
                SystemMessage(content=system_prompt),
                *recent_messages,
                HumanMessage(content=f"Latest Query: {original_query}")
            ]

            try:
                rewriter_llm = llm_service.get_structured_quaternary_model(OptimizedSearchQuery)
                rewritten_result = await rewriter_llm.ainvoke(messages)
                optimized_query = rewritten_result.search_query

                if len(optimized_query) > max_query_length:
                    logger.warning(f"[Web Search] ⚠️ LLM hallucinated query too long ({len(optimized_query)} chars). Using original.")
                    optimized_query = original_query
                else:
                    logger.debug(f"[Web Search] 🪄 Optimized query: '{optimized_query}' (Original: '{original_query}')")
            except Exception as e:
                logger.warning(f"[Web Search] Query optimization failed: {e}. Falling back to original query.")
                optimized_query = original_query

        # 2. Execute search
        new_web_results = []
        num_results_to_fetch = settings.WEB_SEARCH_NUM_RESULTS

        try:
            raw_results = await asyncio.to_thread(
                searx_wrapper.results, 
                optimized_query, 
                num_results=num_results_to_fetch
            )

            for res in raw_results:
                web_item = WebResult(
                    snippet=res.get("snippet", "No snippet available"),
                    title=res.get("title", "No Title"),
                    link=res.get("link", ""),
                    engines=res.get("engines", []),
                    category=res.get("category", "general")
                )
                new_web_results.append(web_item)
        except asyncio.TimeoutError:
            logger.error(f"SearXNG search timed out after {settings.WEB_SEARCH_TIMEOUT_SEC} seconds.")
            new_web_results.append(
                WebResult(
                    snippet="Web search failed: The search engine took too long to respond.",
                    title="Search Timeout",
                    link="", engines=[], category="error"
                )
            )
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
