import time
from typing import List, Literal, Union, cast
from loguru import logger


from app.common.constants import ObservationType
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.routing.route_action import RouteDecision, get_routing_destinations
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.core.prompts.router_prompts import ROUTER_FINAL_STATE_ENFORCEMENT, ROUTER_SYSTEM_INSTRUCTIONS

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import render_text_description_and_args, BaseTool
from langgraph.types import Command
from app.utils.graph.context_utils import format_tools_for_prompt, get_recent_messages, format_optimized_workspace

def make_router_node(
    llm_service: LLMService,
    available_tools: dict[str, BaseTool]
):
    @tracing(observation_type=ObservationType.CHAIN)
    async def router(state: AgentState) -> Command[
        Literal[
            AgentGraphNode.RAG,
            AgentGraphNode.TOOL,
            AgentGraphNode.WEB_SEARCH,
            AgentGraphNode.INNER_SYNTHESIZER,
        ]
    ]:
        settings = get_settings()
        logger.debug("[Router] 🧭 Starting intent analysis")

        current_iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)

        if current_iteration >= max_iterations:
            return Command(goto=AgentGraphNode.INNER_SYNTHESIZER, update={"iteration_count": current_iteration + 1})

        start_time = time.time()
        query = state["query"]

        # 1. Block A: Optimized Workspace + Base Instructions + Summary
        router_llm = llm_service.get_structured_secondary_model(RouteDecision)
        tool_list_str = format_tools_for_prompt(available_tools, include_params=True)
        workspace_context = format_optimized_workspace(state.get("active_project"), state.get("active_datasets"), state.get("system_datasets"))

        sys_msg_1 = SystemMessage(content=ROUTER_SYSTEM_INSTRUCTIONS.format(
            workspace_context=workspace_context,
            extracted_knowledge=str(state.get("extracted_knowledge", [])),
            tool_list_str=tool_list_str,
            conversation_summary=state.get('summary', 'No summary available.')
        ))

        # 2. Block B: Recent Message History (Deduplicated)
        recent_messages = get_recent_messages(state.get("messages", []), last_k_turns=3)
        if recent_messages and recent_messages[-1].content == query:
            recent_messages = recent_messages[:-1]
        
        history_header = [SystemMessage(content="--- RECENT CONVERSATION HISTORY ---")] if recent_messages else []

        # 3. Block C: The Current Intent Analysis (Highest Priority)
        # We append enforcement instructions here to ensure they are the very last thing the LLM sees
        
        rag_results = state.get("rag_results", [])
        tool_results = state.get("tool_results", [])
        web_results = state.get("web_results", [])

        available_intents_list = ["- 'direct_answer'", "- 'all'", "- 'tool_only'"]
        if not web_results: available_intents_list.append("- 'web_search'")
        if not rag_results: available_intents_list.append("- 'rag_only'")
        
        intents_str = "\n".join(available_intents_list)
        execution_history = "<info>No actions executed yet.</info>" # Simplified for space

        sys_msg_2 = SystemMessage(content=ROUTER_FINAL_STATE_ENFORCEMENT.format(
            execution_history=execution_history,
            failover_instruction="<info>No failed tools.</info>",
            intents_str=intents_str
        ))

        task_msg = HumanMessage(content=f"--- CURRENT TASK ---\nUser Query: {query}")

        messages_to_send: List[BaseMessage] = [sys_msg_1] + history_header + recent_messages + [sys_msg_2, task_msg]

        try:
            decision: RouteDecision = await router_llm.ainvoke(messages_to_send)
        except Exception as e:
            logger.exception("[Router] ❌ LLM routing failed")
            raise e
        
        destinations = cast(
            Union[
                Literal[
                    AgentGraphNode.RAG,
                    AgentGraphNode.TOOL,
                    AgentGraphNode.WEB_SEARCH,
                    AgentGraphNode.INNER_SYNTHESIZER,
                ],
                List[
                    Literal[
                        AgentGraphNode.RAG,
                        AgentGraphNode.TOOL,
                        AgentGraphNode.WEB_SEARCH,
                        AgentGraphNode.INNER_SYNTHESIZER,
                    ]
                ]
            ],
            get_routing_destinations(decision.intent)
        )

        elapsed = int((time.time() - start_time) * 1000)

        return Command(
            goto=destinations,
            update={
                "required_tools": decision.required_tools,
                "rag_query": decision.rag_query,
                "web_query": decision.web_query,
                "iteration_count": current_iteration + 1,
                "last_intent": decision.intent,
                "router_guidance": decision.reasoning
            }
        )

    return router
