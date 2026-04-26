import asyncio
from enum import StrEnum
import time
from typing import List, Literal, cast
from langfuse import observe
from langgraph.graph import END
from loguru import logger
from pydantic import BaseModel, Field

from app.common.constants import ObservationType
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.core.prompts.synthesizer_prompts import SYNTHESIZER_SYSTEM_PROMPT, SYNTHESIZER_FINAL_WARNING

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
    # @tracing(observation_type=ObservationType.CHAIN)
    async def synthesizer(state: AgentState) -> Command[
        Literal[AgentGraphNode.SUMMARIZER, AgentGraphNode.ROUTER]
    ]:
        logger.debug("[Synthesizer] ✍️ Generating final response")
        
        settings = get_settings()
        synthesizer_timeout = getattr(settings, 'synthesizer_timeout_sec', 45.0) 

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
            final_warning = SYNTHESIZER_FINAL_WARNING
        
            
        system_prompt = SYNTHESIZER_SYSTEM_PROMPT.format(
            query=query,
            guidance_text=guidance_text,
            tool_list_str=tool_list_str,
            context_string=context_string,
            final_warning=final_warning
        )

        llm = llm_service.get_structured_secondary_model(SynthesizerOutput)

        messages_to_send: List[BaseMessage] = [
            SystemMessage(content=system_prompt)
        ]

        if messages:
            messages_to_send.extend(messages)

        try:
            result = await asyncio.wait_for(
                llm.ainvoke(messages_to_send),
                timeout=synthesizer_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"[Synthesizer] ❌ LLM generation timed out after {synthesizer_timeout} seconds.")
            return Command(
                goto=AgentGraphNode.SUMMARIZER,
                update={
                    "final_answer": "I apologize, but synthesizing this massive amount of data took too long and timed out. Could you please narrow down your question?",
                    "is_complete": True
                }
            )
        except Exception as e:
            logger.error(f"[Synthesizer] ❌ LLM Generation failed: {e}")
            return Command(
                goto=AgentGraphNode.SUMMARIZER,
                update={
                    "final_answer": "I apologize, but I encountered an error while formatting the synthesized information.",
                    "is_complete": True
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