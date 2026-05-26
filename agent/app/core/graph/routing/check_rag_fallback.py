# from typing import Literal

# from loguru import logger
# from langgraph.types import Command

# from app.core.graph.nodes.agent_graph_node import AgentGraphNode
# from app.core.graph.state.agent_state import AgentState


# after_rag_fallback_node = Literal["web_search", "synthesizer"]
# def check_rag_fallback(state: AgentState) -> after_rag_fallback_node:
#     """
#     Checks if RAG returned useful documents. 
#     If not, routes to web search. Otherwise, proceeds to synthesizer.
#     """
#     rag_results = state.get("rag_results", [])

#     if not rag_results:
#         logger.warning("RAG returned no results. Falling back to Web Search.")
#         return AgentGraphNode.WEB_SEARCH.value
        
#     # Optional: You can also check relevance scores if your RAGResult populates them
#     # top_score = max((doc.relevance_score for doc in rag_results if doc.relevance_score), default=0)
#     # if top_score < 0.5:
#     #     logger.warning("RAG results too low quality. Falling back to Web Search.")
#     #     return AgentGraphNode.WEB_SEARCH.value

#     logger.debug("RAG found relevant documents. Proceeding to Synthesizer.")
#     return AgentGraphNode.SYNTHESIZER.value