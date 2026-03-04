# from app.core.graph.state.agent_state import AgentState
# from langchain_core.messages import HumanMessage, SystemMessage

# from app.services.llm import llm_service

# async def query_analyzer(state: AgentState) -> dict:
#     """
#     Analyzes the user query to determine routing intent and which tools are needed.

#     Uses a structured LLM call with a system prompt focused on intent classification.
#     The result drives which nodes are activated next (RAG, tools, or both).

#     Populates:
#         - intent: one of rag_only | tool_only | both | unclear
#         - required_tools: list of tool names needed (e.g. ["blast", "web_search"])
#         - sources_used: appends an llm_internal record for traceability
#     """

#     system_msg = SystemMessage(content=
#         """You are a query routing agent for a sugarcane genomics system.
#         Classify the user's intent and identify required tools.
#         Always respond in valid JSON only, no extra text.

#         Available tools: blast, synteny, web_search, code_interpreter
#         Intent options: rag_only | tool_only | both | unclear
#         """
#     )

#     human_msg = HumanMessage(content=
#         f"""
#             Query: {state["query"]}

#             Respond with JSON:
#             {{
#                 "intent": "...",
#                 "required_tools": [...],
#                 "needs_rag": true/false,
#                 "reasoning": "..."
#             }}
#         """
#     )

#     result = await 