import time
from loguru import logger
from pydantic import BaseModel, Field

from app.core.graph.state.agent_state import AgentState
from app.core.graph.workflow.agent_workflow import SynthesizerDecision
from app.services.llm.llm_service import LLMService

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

# Define how the LLM should output its answer
class SynthesizerOutput(BaseModel):
    answer: str = Field(description="The response to the user based on the provided contexts.")
    is_complete: bool = Field(description="Set to True if you fully answered the user's original query. Set to False if you are missing information.")
    missing_info: str = Field(description="If is_complete is False, explicitly state what specific information is missing so the Router can search for it next. If complete, leave empty.")
    
def make_synthesizer_node(llm_service: LLMService):

    async def synthesizer(state: AgentState) -> dict:
        logger.debug("[Synthesizer] ✍️ Generating final response")
        
        current_iteration = state.get("iteration_count", 0)
        query = state["query"]

        # Format context
        rag_context = "\n".join([f"- [Doc: {r.get('source_file')}] {r.get('content')}" for r in state.get("rag_results", [])])
        web_context = "\n".join([f"- [{r.get('title')}] ({r.get('link')}): {r.get('snippet')}" for r in state.get("web_results", [])])
        tool_context = "\n".join([f"- [{r.get('tool_name')}] Status: {r.get('status')}\nOutput: {r.get('output')}" for r in state.get("tool_results", [])])

        context_string = f"""
            --- RAG KNOWLEDGE ---
            {rag_context if rag_context else "No RAG data found."}

            --- WEB SEARCH RESULTS ---
            {web_context if web_context else "No web data found."}

            --- TOOL OUTPUTS ---
            {tool_context if tool_context else "No tool data found."}
        """

        prompt = f"""
            You are an expert Bioinformatics Assistant. Use the provided context to answer the user's query.
            
            User Query: {query}
            
            Context:
            {context_string}
            
            INSTRUCTIONS:
            - Synthesize the information from all available contexts.
            - If you can fully answer the query, set 'is_complete' to True.
            - If you cannot fully answer the query because information is missing from the context, answer what you can, set 'is_complete' to False, and state exactly what is missing in the 'missing_info' field.
        """

        llm = llm_service.get_model().with_structured_output(SynthesizerOutput)

        try:
            raw_result = await llm.ainvoke(prompt)
            result = SynthesizerOutput.model_validate(raw_result)
        except Exception as e:
            logger.error(f"[Synthesizer] LLM Generation failed: {e}")
            return {
                "final_answer": "I apologize, but I encountered an error while synthesizing the information.",
                "is_complete": True, # Force complete on fatal error to avoid infinite loops
                "iteration_count": current_iteration + 1
            }

        logger.debug(f"[Synthesizer] Complete? {result.is_complete} | Missing: {result.missing_info}")
        
        # 4. Prepare State Updates
        updates = {
            "final_answer": result.answer,
            "is_complete": result.is_complete,
            "iteration_count": current_iteration + 1 # Increment loop counter!
        }

        # 5. The Breadcrumb Logic - Communicate with the Router!
        if not result.is_complete:
            logger.warning(f"[Synthesizer] Missing info: '{result.missing_info}'. Triggering loop back to Router.")
            feedback_msg = AIMessage(
                content=f"Internal Note: I partially answered the user, but I am still missing: {result.missing_info}. "
                        f"Please route to a different tool (like web_search or tool_execution) to find this missing information."
            )
            updates["messages"] = [feedback_msg]
            
        return updates

    return synthesizer