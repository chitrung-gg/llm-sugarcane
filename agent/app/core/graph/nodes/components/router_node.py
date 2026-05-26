import time
from typing import List, Dict, Any
from loguru import logger

from app.schemas.agent.router import RouteDecision
from app.common.constants import ObservationType
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.core.prompts.router_prompts import ROUTER_FINAL_STATE_ENFORCEMENT, ROUTER_SYSTEM_INSTRUCTIONS

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import BaseTool

from app.utils.graph.context_utils import format_optimized_context, format_tools_for_prompt, get_recent_messages

def make_router_node(
    llm_service: LLMService,
    available_tools: dict[str, BaseTool]
):
    @tracing(observation_type=ObservationType.CHAIN)
    async def router(state: AgentState) -> Dict[str, Any]:
        """
        Router Node that analyzes user intent and prepares the execution state.
        """
        start_time = time.time()
        query = state["query"]

        # 1. Prepare LLM Configurations and System Prompts
        router_llm = llm_service.get_structured_secondary_model(RouteDecision)
        tool_list_str = format_tools_for_prompt(available_tools, include_params=True)
        workspace_context = format_optimized_context(state.get("active_project"), state.get("active_datasets"))

        sys_msg_1 = SystemMessage(content=ROUTER_SYSTEM_INSTRUCTIONS.format(
            workspace_context=workspace_context,
            extracted_knowledge=str(state.get("extracted_knowledge", [])),
            tool_list_str=tool_list_str,
            conversation_summary=state.get('summary', 'No summary available.')
        ))

        # 2. Extract and Format Message History
        recent_messages = get_recent_messages(state.get("messages", []), last_k_turns=3)
        if recent_messages and recent_messages[-1].content == query:
            recent_messages = recent_messages[:-1]
        
        history_header = [SystemMessage(content="--- RECENT CONVERSATION HISTORY ---")] if recent_messages else []

        # 3. Analyze Current Retrieval Execution History
        available_intents_list = [
            "- 'direct_answer'", 
            "- 'all'", 
            "- 'rag_only'", 
            "- 'tool_only'", 
            "- 'web_search'"
        ]
        intents_str = "\n".join(available_intents_list)

        sys_msg_2 = SystemMessage(content=ROUTER_FINAL_STATE_ENFORCEMENT.format(
            execution_history=str(state.get("past_steps", [])),
            failover_instruction="If previous attempts failed, try a different strategy.",
            intents_str=intents_str
        ))

        task_msg = HumanMessage(content=f"--- CURRENT TASK ---\nUser Query: {query}")

        messages_to_send: List[BaseMessage] = [sys_msg_1] + history_header + recent_messages + [sys_msg_2, task_msg]

        # 4. Invoke LLM for Intent Classification
        try:
            decision: RouteDecision = await router_llm.ainvoke(messages_to_send)
        except Exception as e:
            logger.exception("[Router] LLM routing failed")
            raise e
        
        # 5. Return Raw State Updates
        return {
            "intent": decision.intent,
            "required_tools": decision.required_tools,
            "rag_query": decision.rag_query,
            "web_query": decision.web_query,
            "last_intent": decision.intent,
            "router_guidance": decision.reasoning
        }

    return router