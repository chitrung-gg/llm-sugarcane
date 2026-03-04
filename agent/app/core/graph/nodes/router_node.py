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

        system_instructions = """You are an expert routing assistant for a Sugarcane Genomics system.
            Your job is to analyze the user's query and route it to the correct execution path.
            - Choose 'rag_only' if the query asks for literature, research papers, or general knowledge.
            - Choose 'tool_only' if the query requires executing code, BLAST, or Synteny analysis.
            - Choose 'both' if the query requires BOTH literature search and tool execution.
            - Choose 'unclear' if the query is a simple greeting or doesn't require any search.
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
            messages_to_send = (
                [messages_to_send[0]]
                + state["messages"]
                + [messages_to_send[1]]
            )

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