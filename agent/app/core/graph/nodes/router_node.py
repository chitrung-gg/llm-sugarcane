import time
from typing import Literal, Union
from loguru import logger

from app.core.graph.routing.route_action import RouteDecision, get_routing_destinations
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Command

after_router_node = Literal["rag_execution", "tool_execution", "web_search", "synthesizer"]

def make_router_node(llm_service: LLMService):
    async def router(state: AgentState) -> Command[after_router_node]:
        logger.debug("[Router] 🧭 Starting intent analysis")

        start_time = time.time()

        query = state["query"]
        logger.debug(f"[Router] Query: {query}")

        llm = llm_service.get_model()
        router_llm = llm.with_structured_output(RouteDecision)

        system_instructions = """
            You are an expert routing assistant for a Sugarcane Genomics system.
            Your job is to analyze the user's query and route it to the correct execution path.

            CRITICAL ROUTING RULES:
            - Choose 'direct_answer': If the user asks to summarize, translate, or answer questions strictly about a file they just uploaded, and you can see the file's content in the chat history.
            - Choose 'all' (RECOMMENDED DEFAULT): For general sugarcane biology questions.
            - Choose 'web_search': For the *latest* news, external web data, or broad scientific facts.
            - Choose 'rag_only': ONLY if the query explicitly targets our internal database.
            - Choose 'tool_only': For executing bioinformatic tools (BLAST/Synteny).
            - Choose 'unclear': For simple greetings.
        """
        
        user_input = f"User Query: {query}"

        messages_to_send = [
            SystemMessage(content=system_instructions),
            HumanMessage(content=user_input),
        ]

        # Include previous chat history if it exists
        if state.get("messages"):
            logger.debug(
                f"[Router] Including chat history | messages={len(state['messages'])}"
            )
            messages_to_send.extend(state["messages"])
        
        logger.debug(
            f"[Router] Sending {len(messages_to_send)} messages to LLM"
        )

        try:
            raw_decision = await router_llm.ainvoke(messages_to_send)
            decision = RouteDecision.model_validate(raw_decision)

        except Exception as e:
            logger.exception("[Router] ❌ LLM routing failed")
            raise
        
        destinations = get_routing_destinations(decision.intent)

        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[Router] ✅ Decision made | "
            f"intent={decision.intent} | "
            f"tools={decision.required_tools} | "
            f"latency={elapsed}ms"
        )

        return Command(
            goto=destinations,
            update={
                "required_tools": decision.required_tools
            }
        )

    return router