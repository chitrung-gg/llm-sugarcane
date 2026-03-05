import time
from loguru import logger

from app.core.graph.routing.route_action import RouteDecision
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService

from langchain_core.messages import SystemMessage, HumanMessage


def make_router_node(llm_service: LLMService):

    async def router(state: AgentState) -> dict:
        logger.debug("[Router] 🧭 Starting intent analysis")

        start_time = time.time()

        query = state["query"]
        logger.debug(f"[Router] Query: {query}")

        llm = llm_service.get_model()
        router_llm = llm.with_structured_output(RouteDecision)

        system_instructions = """
            You are an expert routing assistant for a Sugarcane Genomics system.
            Your job is to analyze the user's query and route it to the correct execution path.

            RULES FOR ROUTING:
            - Choose 'rag_only': If the query asks for static knowledge, literature, research papers, or general sugarcane biology that is stored in our internal database.
            - Choose 'tool_only': If the query requires executing bioinformatic tools, local BLAST, or Synteny analysis.
            - Choose 'web_search': If the query asks for the *latest* news, external web data, CIRAD databases, or up-to-date information not likely in a static local database.
            - Choose 'all': If the query requires a combination of searches (e.g., checking internal literature AND searching the web for recent updates).
            - Choose 'unclear': If the query is a simple greeting (e.g., 'Hello', 'Who are you?') or does not require looking up any data.
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

        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[Router] ✅ Decision made | "
            f"intent={decision.intent} | "
            f"tools={decision.required_tools} | "
            f"latency={elapsed}ms"
        )

        return {
            "intent": decision.intent,
            "required_tools": decision.required_tools,
        }

    return router