import time
from typing import Literal, cast
from langgraph.graph import END
from loguru import logger
from pydantic import BaseModel, Field

from app.core.graph.routing.check_if_resolved import check_if_resolved
from app.core.graph.state.agent_state import AgentState
from app.core.graph.workflow.agent_workflow import SynthesizerDecision
from app.services.llm.llm_service import LLMService

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.types import Command

# after_synthesizer_node to go to after completed this step
after_synthesizer_node = Literal["router", "__end__"]

# Define how the LLM should output its answer
class SynthesizerOutput(BaseModel):
    answer: str = Field(description="The response to the user based on the provided contexts.")
    is_complete: bool = Field(description="Set to True if you fully answered the user's original query. Set to False if you are missing information.")
    missing_info: str = Field(description="If is_complete is False, explicitly state what specific information is missing so the Router can search for it next. If complete, leave empty.")
    
def make_synthesizer_node(llm_service: LLMService):

    async def synthesizer(state: AgentState) -> Command[after_synthesizer_node]:
        logger.debug("[Synthesizer] ✍️ Generating final response")
        
        current_iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)
        query = state["query"]

        # Extract the uploaded file text from the messages
        file_context = ""
        for msg in state.get("messages", []):
            # Look for the SystemMessage created by the Input Analyzer
            if getattr(msg, "content", "").startswith("The user has uploaded the following files"):
                file_context = msg.content

        # Format context
        rag_context = "\n".join([f"- [Doc: {r.get('source_file')}] {r.get('content')}" for r in state.get("rag_results", [])])
        web_context = "\n".join([f"- [{r.get('title')}] ({r.get('link')}): {r.get('snippet')}" for r in state.get("web_results", [])])
        tool_context = "\n".join([f"- [{r.get('tool_name')}] Status: {r.get('status')}\nOutput: {r.get('output')}" for r in state.get("tool_results", [])])

        context_string = f"""
            --- UPLOADED FILE CONTENT ---
            {file_context if file_context else "No files uploaded."}
            
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
            logger.error("[Synthesizer] LLM Generation failed: {error}", error=str(e))
            # Force END on fatal errors to avoid loops
            updates = {
                "final_answer": "I apologize, but I encountered an error while synthesizing the information.",
                "is_complete": True, 
                "iteration_count": current_iteration + 1
            }
            return Command(
                goto="__end__",         # langgraph.graph.END equals to __end__ 
                update=updates
            )

        logger.debug(
            "[Synthesizer] Complete? {is_complete} | Missing: {missing}", 
            is_complete=result.is_complete, missing=result.missing_info
        )
        
        # Prepare State Updates
        updates = {
            "final_answer": result.answer,
            "is_complete": result.is_complete,
            "iteration_count": current_iteration + 1 # Increment loop counter!
        }

        # Evaluator-optimizer pattern
        if not result.is_complete:
            feedback_msg = AIMessage(
                content=f"Internal Note: I partially answered the user, but I am still missing: {result.missing_info}. "
                        f"Please route to a different tool to find this missing information."
            )
            updates["messages"] = [feedback_msg]
        
        preview_state = cast(AgentState, {**state, **updates})
        
        destination = check_if_resolved(preview_state)

        return Command(
            goto=destination,
            update=updates
        )


    return synthesizer