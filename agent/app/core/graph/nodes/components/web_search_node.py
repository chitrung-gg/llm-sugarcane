import asyncio
from enum import StrEnum
import json
import time
from typing import List, Literal, cast
from langfuse import observe
from loguru import logger
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.types import Command
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.documents import Document

from pydantic import BaseModel, Field

from app.services.llm.reranker_service import RerankerService
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
    llm_service: LLMService,
    reranker_service: RerankerService
):
    """Factory to create the web search node with injected dependency."""
    @tracing(observation_type=ObservationType.RETRIEVER)
    async def web_search(state: AgentState) -> dict:
        settings = get_settings()

        logger.debug("--- TRIGGERING SEARXNG WEB SEARCH ---")
        start_time = time.time()

        # Check if the Router provided a specific search query
        original_query = state["query"]
        optimized_query = state.get("web_query")
        
        if not optimized_query:
            # Fallback check for tool calls if web_query is missing
            required_tools = state.get("required_tools", [])
            for tool_call in required_tools:
                if tool_call.name == "web_search" and "query" in tool_call.args:
                    optimized_query = tool_call.args["query"]
                    break

        if optimized_query:
            logger.info(f"[Web Search] Using pre-optimized query: '{optimized_query}'")
        else:
            
            max_query_length = settings.WEB_SEARCH_MAX_QUERY_LENGTH

            # 1. Query Optimization (Skip if already provided)
            logger.info("[Web Search] No pre-optimized query found. Rewriting...")
            system_prompt = WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT.format(
                conversation_summary=state.get("summary", "No prior context."),
                user_question=original_query
            )

            # Include recent messages for context
            recent_messages = get_recent_messages(state.get("messages", []), last_k_turns=3)

            messages: List[BaseMessage] = [
                SystemMessage(content=system_prompt),
                *recent_messages,
                HumanMessage(content=f"Latest Query: {original_query}")
            ]

            try:
                rewriter_llm = llm_service.get_structured_quaternary_model(OptimizedSearchQuery)
                rewritten_result: OptimizedSearchQuery = await rewriter_llm.ainvoke(messages)
                optimized_query = rewritten_result.search_query

                if len(optimized_query) > max_query_length:
                    logger.warning(f"[Web Search] LLM output query too long ({len(optimized_query)} chars). Using original.")
                    optimized_query = original_query
                else:
                    logger.debug(f"[Web Search] Optimized query: '{optimized_query}' (Original: '{original_query}')")
            except Exception as e:
                logger.warning(f"[Web Search] Query optimization failed: {e}. Falling back to original query.")
                optimized_query = original_query

        # 2. Execute search
        num_results_to_fetch = settings.WEB_SEARCH_NUM_RESULTS

        try:
            raw_results = await asyncio.to_thread(
                searx_wrapper.results, 
                optimized_query, 
                num_results=num_results_to_fetch
            )
        except asyncio.TimeoutError:
            logger.error(f"SearXNG search timed out after {settings.WEB_SEARCH_TIMEOUT_SEC} seconds.")
            raw_results = []
        except Exception as e:
            logger.error("SearXNG search failed: {error}", error=str(e))
            raw_results = []

        web_docs = []
        for res in raw_results:
            logger.info(f"[Web Search] Sample result: {json.dumps(res, default=str)}")
            snippet = res.get("snippet", "")
            if snippet:
                web_docs.append(
                    Document(
                        page_content=f"[WEB SEARCH] {snippet}",
                        metadata={
                            "url": res.get("link", ""),
                            "title": res.get("title", "")
                        }
                    )
                )

        # 4. Rerank the Web Snippets (High Precision)
        logger.debug(f"[Web Search] Reranking {len(web_docs)} web snippets...")
        
        if not web_docs:
            return {"web_results": []}
            
        reranked_docs = await asyncio.to_thread(
            reranker_service.rerank_documents,
            documents=web_docs,
            query=original_query,
            top_k=settings.WEB_SEARCH_NUM_RESULTS,
        )

        final_web_results = []

        for doc in reranked_docs:
            raw_score = doc.metadata.get("relevance_score", 0.0)
            relevance_score = float(raw_score) 

            final_web_results.append({
                "snippet": doc.page_content,
                "title": doc.metadata.get("title", ""),
                "link": doc.metadata.get("url", ""),
                "score": relevance_score
            })

        logger.info(f"[Web Search] Kept {len(final_web_results)} highly relevant snippets.")

        execution_time = int((time.time() - start_time) * 1000)

        return {"web_results": final_web_results}

    return web_search
