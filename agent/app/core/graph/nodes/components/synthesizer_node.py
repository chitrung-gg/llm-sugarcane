import asyncio
from enum import StrEnum
import time
from typing import List, Literal, cast
from langfuse import observe
from langgraph.graph import END
from loguru import logger
from pydantic import BaseModel, Field

from app.core.graph.state.planner_state import AgentStepObservation
from app.common.constants import AgentIntent, ObservationType, PlanStatus
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.core.prompts.synthesizer_prompts import SYNTHESIZER_SYSTEM_PROMPT, SYNTHESIZER_FINAL_WARNING
from app.schemas.agent.synthesizer import SynthesizerOutput

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import BaseTool, render_text_description_and_args
from langgraph.types import Command
    
def make_synthesizer_node(llm_service: LLMService, available_tools: dict[str, BaseTool]):
    @tracing(observation_type=ObservationType.CHAIN)
    async def synthesizer(state: AgentState) -> Command[
        Literal[AgentGraphNode.END_NODE, AgentGraphNode.ROUTER]
    ]:
        logger.debug("[Synthesizer] ✍️ Generating final response")
        
        settings = get_settings()
        synthesizer_timeout = settings.SYNTHESIZER_TIMEOUT_SEC

        current_iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)
        query = state["query"]
        messages = state.get("messages", [])

        # 1. Rebuild Workspace Context from New State
        active_project = state.get("active_project")
        active_datasets = state.get("active_datasets", [])
        
        p_name = active_project.get("project_name", "Default Project") if active_project else "Default Project"
        workspace_str = f"ACTIVE PROJECT: {p_name}\n"
        
        if active_datasets:
            workspace_str += "ACTIVE DATASETS:\n"
            for ds in active_datasets:
                workspace_str += f"- {ds.get('dataset_name')} (ID: {ds.get('dataset_id')})\n"
        else:
            workspace_str += "No specific datasets active.\n"

        # 2. Format execution context
        rag_context = "\n".join([f"- [Doc: {r.get('source_file')}] {r.get('content')}" for r in state.get("rag_results", [])])
        web_context = "\n".join([f"- [{r.get('title')}] ({r.get('link')}): {r.get('snippet')}" for r in state.get("web_results", [])])
        tool_context = "\n".join([f"- [{r.get('tool_name')}] Status: {r.get('status')}\nOutput: {r.get('output')}" for r in state.get("tool_results", [])])

        context_string = f"""
            --- ACTIVE WORKSPACE/FILE CONTEXT ---
            {workspace_str }
            
            --- RAG KNOWLEDGE ---
            {rag_context if rag_context else "No RAG data found."}

            --- WEB SEARCH RESULTS ---
            {web_context if web_context else "No web data found."}

            --- TOOL OUTPUTS (Check here for successful actions) ---
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

        is_final_attempt = current_iteration >= max_iterations
        if is_final_attempt:
            final_warning = SYNTHESIZER_FINAL_WARNING
        
            
        system_prompt = SYNTHESIZER_SYSTEM_PROMPT.format(
            query=query,
            guidance_text=guidance_text,
            tool_list_str=tool_list_str,
            context_string=context_string,
            final_warning=final_warning
        )

        # Tier 1 for best quality synthesis
        llm = llm_service.get_structured_primary_model(SynthesizerOutput)

        messages_to_send: List[BaseMessage] = [
            SystemMessage(content=system_prompt)
        ]

        if messages:
            messages_to_send.extend(messages)

        try:
            result = await llm.ainvoke(messages_to_send)
            # result = await asyncio.wait_for(
            #     llm.ainvoke(messages_to_send),
            #     timeout=synthesizer_timeout
            # )
        except asyncio.TimeoutError:
            logger.error(f"[Synthesizer] ❌ LLM generation timed out after {synthesizer_timeout} seconds.")
            return Command(
                goto=AgentGraphNode.END_NODE,
                update={
                    "final_answer": "I apologize, but synthesizing this massive amount of data took too long and timed out. Could you please narrow down your question?",
                    "is_complete": True
                }
            )
        except Exception as e:
            logger.error(f"[Synthesizer] ❌ LLM Generation failed: {e}")
            return Command(
                goto=AgentGraphNode.END_NODE,
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
            "messages": [
                AIMessage(
                    content=result.answer,
                    additional_kwargs={"execution_id": str(state.get("execution_id"))}
                )
            ]
        }
        
        # Determine destination
        if not result.is_complete and not is_final_attempt and state.get("last_intent") != AgentIntent.DIRECT_ANSWER:
            # 1. Step failed or needs more info -> Loop back to ROUTER
            logger.warning("⚠️ Answer incomplete. Sending back to ROUTER.")
            updates["messages"] = [
                AIMessage(
                    content=f"Thought: I am still missing info: {result.missing_info}",
                    additional_kwargs={"is_thought": True, "execution_id": str(state.get("execution_id"))}
                )
            ]
            destination = AgentGraphNode.ROUTER
        else:
            # 2. Inner task is complete. We update the final_answer and exit the INNER graph.
            # The Outer Executor will catch this answer, update past_steps, and decide what to do next.
            logger.info("[Synthesizer] Answer complete. Exiting inner graph.")
            destination = AgentGraphNode.END_NODE
        return Command(
            goto=destination,
            update=updates
        )

    return synthesizer
