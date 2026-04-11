from enum import StrEnum
import time
from typing import Literal, cast
from langgraph.graph import END
from loguru import logger
from pydantic import BaseModel, Field

from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.core.graph.workflow.agent_workflow import SynthesizerDecision
from app.services.llm.llm_service import LLMService

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.types import Command


# Define how the LLM should output its answer
class SynthesizerOutput(BaseModel):
    answer: str = Field(description="The response to the user based on the provided contexts.")
    is_complete: bool = Field(description="Set to True if you fully answered the user's original query. Set to False if you are missing information.")
    missing_info: str = Field(description="If is_complete is False, explicitly state what specific information is missing so the Router can search for it next. If complete, leave empty.")
    
def make_synthesizer_node(llm_service: LLMService):

    async def synthesizer(state: AgentState) -> Command[
        Literal[AgentGraphNode.SUMMARIZER, AgentGraphNode.ROUTER]
    ]:
        logger.debug("[Synthesizer] ✍️ Generating final response")
        
        current_iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)
        query = state["query"]
        messages = state.get("messages", [])

        # Detect if this is the final allowed loop
        is_final_attempt = current_iteration >= max_iterations

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

        # Dynamically add instructions if the agent is about to give up
        final_warning = ""
        if is_final_attempt:
            final_warning = """
            ⚠️ CRITICAL INSTRUCTION: This is your final attempt to answer. If you still do not have the complete information, you MUST:
            1. Provide whatever partial answer you can in the 'answer' field.
            2. At the end of the 'answer' field, add a clear note stating exactly what information you could not find.
            3. Suggest alternative search queries, specific tools, or ask the user to upload a relevant document (like a specific research paper) to help you answer it.
        """
        
            
        system_prompt = f"""
            You are an expert Bioinformatics Assistant. Use the provided context to answer the user's query.
            User Query: {query}
            
            Context:
            {context_string}
            
            INSTRUCTIONS:
            - Synthesize the information from all available contexts.
            - If you can fully answer the query, set 'is_complete' to True.
            - If you cannot fully answer the query because information is missing from the context, answer what you can, set 'is_complete' to False, and state exactly what is missing in the 'missing_info' field.
            {final_warning} 
        """

        llm = llm_service.get_primary_model().with_structured_output(SynthesizerOutput)

        try:
            llm_input = [SystemMessage(content=system_prompt)] + messages
            raw_result = await llm.ainvoke(llm_input)
            result = SynthesizerOutput.model_validate(raw_result)
        except Exception as e:
            logger.error("[Synthesizer] LLM Generation failed: {error}", error=str(e))
            # Force END on fatal errors to avoid loops
            return Command(
                goto=AgentGraphNode.SUMMARIZER,
                update={
                    "final_answer": "I apologize, but I encountered an error while synthesizing the information.",
                    "is_complete": True, 
                    "iteration_count": current_iteration + 1
                }
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
        if is_final_attempt:
            logger.error("🛑 Max iterations reached! Forcing the graph to SUMMARIZER.")
            updates["messages"] = [AIMessage(content=result.answer)]
            destination = AgentGraphNode.SUMMARIZER
            
        elif result.is_complete:
            logger.debug("✅ Answer complete. Sending to SUMMARIZER.")
            updates["messages"] = [AIMessage(content=result.answer)]
            destination = AgentGraphNode.SUMMARIZER
            
        else:
            logger.warning("⚠️ Answer incomplete. Sending back to ROUTER.")
            feedback_msg = AIMessage(
                content=f"Internal Thought: I partially answered the user, but I am still missing: {result.missing_info}. "
                        f"I need to route to a different tool to find this missing information."
            )
            updates["messages"] = [feedback_msg]
            destination = AgentGraphNode.ROUTER

        return Command(
            goto=destination,
            update=updates
        )


    return synthesizer