# from typing import List, Literal, Optional, Union

# from loguru import logger

# from langgraph.types import Command
# from app.common.constants import AgentIntent
# from app.core.graph.nodes.agent_graph_node import AgentGraphNode
# from app.schemas.agent.router import RouteDecision


# def get_routing_destinations(intent: str) -> Union[AgentGraphNode, List[AgentGraphNode]]:
#     """Helper function to map LLM intent to graph node destinations."""
#     if intent == AgentIntent.RAG_ONLY:
#         return AgentGraphNode.RAG
#     elif intent == AgentIntent.TOOL_ONLY:  
#         return AgentGraphNode.TOOL
#     elif intent == AgentIntent.WEB_SEARCH: 
#         return AgentGraphNode.WEB_SEARCH
#     elif intent == AgentIntent.ALL:
#         # Return list of nodes so LangGraph runs them in parallel
#         return [
#             AgentGraphNode.RAG, 
#             AgentGraphNode.TOOL, 
#             AgentGraphNode.WEB_SEARCH
#         ] 
#     elif intent == AgentIntent.DIRECT_ANSWER: 
#         return AgentGraphNode.INNER_SYNTHESIZER
#     else:
#         # Fallback for "unclear" or any unexpected intent
#         return AgentGraphNode.INNER_SYNTHESIZER