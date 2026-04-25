import asyncio
from enum import StrEnum
import time
from typing import List, Literal, cast
from langgraph.graph import END
from loguru import logger
from pydantic import BaseModel, Field

from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import BaseTool, render_text_description_and_args
from langgraph.types import Command


# Define how the LLM should output its answer
class SynthesizerOutput(BaseModel):
    answer: str = Field(
        description="The detailed response to the user based on the provided contexts. Always politely explain if specific data could not be found. If the user asks for more information or a deep dive, provide a thorough, multi-paragraph technical explanation extracting all possible details from the context."
    )
    is_complete: bool = Field(
        description="Set to True if you fully answered the query OR if you have exhausted the context and no further tools could possibly help. Set to False ONLY if you specifically need the Router to run a new tool you haven't tried yet."
    )
    missing_info: str = Field(
        description="If is_complete is False, explicitly state what specific information is missing so the Router can search for it next. If complete, leave empty."
    )
    
def make_synthesizer_node(llm_service: LLMService, available_tools: dict[str, BaseTool]):
    @tracing
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

        # Fetch Router Guidance
        router_guidance = state.get("router_guidance", "")
        guidance_text = ""
        if router_guidance:
            guidance_text = f"\nROUTER INSTRUCTIONS FOR THIS RESPONSE: {router_guidance}\n"

        # Render Tool Descriptions
        tool_list_str = render_text_description_and_args(list(available_tools.values()))
        
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
            
            {guidance_text}

            FOR YOUR AWARENESS, YOU HAVE ACCESS TO THESE TOOLS (Even if you aren't executing them right now):
            {tool_list_str}

            If the user asks what tools you have, or how a specific tool works, use the list above to explain it accurately. Do NOT claim you lack a tool if it is in this list.
            
            Context:
            {context_string}
            
            INSTRUCTIONS:
            1. THOROUGHNESS RULE (CRITICAL): 
                - Do not just provide a high-level summary. 
                - Extract EVERY technical detail, gene symbol, methodology, and specific finding mentioned in the provided Context.
                - If the user asks to "explain more" or "tell me more," you MUST expand significantly on each point, providing technical depth from the snippets.
                - Use professional, academic-grade formatting (bullet points, clear headings).

            2. SYMBOL & DATA EXTRACTION:
                - If the context mentions specific numbers (e.g., genome size, chromosome count, dates), you MUST include them.
                - If multiple snippets mention different aspects of the same topic, merge them into a single, detailed section.
            
            3. MISSING DATA FALLBACK (CRITICAL):
                - If the context (like a tool output) fails to find specific data (e.g., a genome, gene, or paper):
                - Look at the Context above. If there are NO Web Search results yet, DO NOT use internal knowledge. You MUST set 'is_complete' to False and set 'missing_info' to: "I need to perform a web search to find recent publications or databases for this specific query."
                - If you HAVE already performed a web search and still cannot find it, only then may you state that the data appears unavailable.
                
            4. CONCEPTUAL QUERIES (INTERNAL KNOWLEDGE):
                - If the query is a general biological explanation or strategy (e.g., "explain polyploidy"), you may use your internal knowledge to answer fully and set 'is_complete' to True.
                
            5. Do NOT confidently state that a genome or gene does not exist just because one specific database tool failed. Always fallback to a web search first!

            {final_warning} 

            ANTI-REPETITION RULE:
            Compare the gathered Context above against your previous messages in the Conversation History. If the tools or databases did not return any NEW information beyond what you have already told the user in previous turns, DO NOT repeat yourself.
        """

        llm = llm_service.get_structured_secondary_model(SynthesizerOutput)

        messages_to_send: List[BaseMessage] = [
            SystemMessage(content=system_prompt)
        ]

        if messages:
            messages_to_send.extend(messages)

        try:
            raw_result = await llm.ainvoke(messages_to_send)
            result = SynthesizerOutput.model_validate(raw_result)
        except Exception as e:
            logger.error("[Synthesizer] LLM Generation failed: {e}", e=e)
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
            # "iteration_count": current_iteration + 1 # Increment loop counter!
        }
        

        last_intent = state.get("last_intent", "")
        router_gave_up = (last_intent == "direct_answer")

        # Evaluator-optimizer pattern
        if is_final_attempt or router_gave_up:
            if router_gave_up:
                logger.warning("🛑 Router chose direct_answer. Forcing the graph to SUMMARIZER to prevent looping.")
            else:
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