import time
from loguru import logger

from app.core.graph.state.agent_state import AgentState
from app.core.graph.workflow.agent_workflow import SynthesizerDecision
from app.services.llm.llm_service import LLMService

from langchain_core.messages import SystemMessage, HumanMessage


def make_synthesizer_node(llm_service: LLMService):

    async def synthesizer(state: AgentState) -> dict:
        logger.debug("[Synthesizer] 🧠 Evaluating context and generating response")

        start_time = time.time()

        # Increment iteration count
        current_iter = state.get("iteration_count", 0) + 1
        max_iter = state.get("max_iterations", 3)

        logger.debug(
            f"[Synthesizer] Iteration {current_iter}/{max_iter}"
        )

        # Circuit Breaker
        if current_iter >= max_iter:
            logger.warning(
                "[Synthesizer] 🚨 Circuit Breaker triggered | "
                f"iteration={current_iter}"
            )
            return {
                "is_complete": True,
                "final_answer": (
                    "System reached the maximum iteration limit "
                    "without finding a conclusive answer."
                ),
                "iteration_count": current_iter,
            }

        # Prepare context
        rag_results = state.get("rag_results", [])
        tool_results = state.get("tool_results", [])

        logger.debug(
            f"[Synthesizer] Context sizes | "
            f"rag_chunks={len(rag_results)} | "
            f"tool_results={len(tool_results)}"
        )

        rag_data = str(rag_results)
        tool_data = str(tool_results)

        system_instructions = """You are an expert Bioinformatics AI Assistant specializing in Sugarcane Genomics.
            Your task is to answer the user's query using ONLY the provided RAG Context and Tools Context.
            
            Rules:
            1. If the provided context is sufficient to answer the query, set 'is_complete' to True and provide a detailed, scientific answer. Cite sources if available.
            2. If the context is NOT sufficient, set 'is_complete' to False and state what specific information is still missing.
        """

        human_content = f"""
            User Query: {state['query']}
            
            --- RAG Context ---
            {rag_data}
            
            --- Tools Context ---
            {tool_data}
        """

        messages_to_send = [
            SystemMessage(content=system_instructions),
            HumanMessage(content=human_content),
        ]

        llm = llm_service.get_model()
        synthesizer_llm = llm.with_structured_output(SynthesizerDecision)

        logger.debug(
            f"[Synthesizer] Sending {len(messages_to_send)} messages to LLM"
        )

        try:
            raw_decision = await synthesizer_llm.ainvoke(messages_to_send)
            decision = SynthesizerDecision.model_validate(raw_decision)
        except Exception:
            logger.exception("[Synthesizer] ❌ LLM invocation failed")
            raise

        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[Synthesizer] LLM response | "
            f"is_complete={decision.is_complete} | "
            f"latency={elapsed}ms"
        )

        if decision.is_complete:
            logger.success(
                "[Synthesizer] ✅ Information sufficient. Finalizing response."
            )
        else:
            logger.info(
                "[Synthesizer] 🔁 Information insufficient. Looping for more context."
            )

        return {
            "is_complete": decision.is_complete,
            "final_answer": decision.final_answer,
            "iteration_count": current_iter,
        }

    return synthesizer