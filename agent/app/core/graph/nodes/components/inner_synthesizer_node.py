import asyncio
from enum import StrEnum
import time
from typing import List, Literal, cast
from langfuse import observe
from langgraph.graph import END
from loguru import logger
from pydantic import BaseModel, Field

from app.core.graph.state.planner_state import AgentStepObservation
from app.common.constants import AgentIntent, ObservationType, PlanStatus, StreamingTag
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.core.prompts.inner_synthesizer_prompts import SYNTHESIZER_SYSTEM_PROMPT, SYNTHESIZER_FINAL_WARNING
from app.schemas.agent.synthesizer import SynthesizerOutput

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from app.utils.graph.context_utils import get_recent_messages, format_optimized_workspace

def make_inner_synthesizer_node(llm_service: LLMService, available_tools: dict[str, BaseTool]):
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

        # 1. Unified Workspace Context (Project + Datasets)
        active_project = state.get("active_project")
        active_datasets = state.get("active_datasets", [])
        system_datasets = state.get("system_datasets", [])
        
        workspace_context = format_optimized_workspace(active_project, active_datasets, system_datasets)

        # 2. Format execution context (with truncation)
        rag_results = state.get("rag_results", [])[:5]
        web_results = state.get("web_results", [])[:5]
        tool_results = state.get("tool_results", [])[-5:] 
        
        rag_context = "\n".join([f"- [Doc: {r.get('source_file')}] {r.get('content')[:1000]}..." for r in rag_results])
        web_context = "\n".join([f"- [{r.get('title')}] ({r.get('link')}): {r.get('snippet')}" for r in web_results])
        tool_context = "\n".join([f"- [{r.get('tool_name')}] Status: {r.get('status')}\nOutput: {r.get('output')[:2000]}..." for r in tool_results])
        knowledge_context = str(state.get("extracted_knowledge", []))

        context_string = f"""
            --- UNIFIED WORKSPACE CONTEXT ---
            {workspace_context}
            
            --- EXTRACTED KNOWLEDGE (FACTS/METADATA) ---
            {knowledge_context if knowledge_context != "[]" else "No structured knowledge extracted yet."}

            --- RAG KNOWLEDGE (Top 5) ---
            {rag_context if rag_context else "No RAG data found."}

            --- WEB SEARCH RESULTS (Top 5) ---
            {web_context if web_context else "No web data found."}

            --- TOOL OUTPUTS (Last 5 calls) ---
            {tool_context if tool_context else "No tool data found."}
        """

        # Fetch Router Guidance
        router_guidance = state.get("router_guidance", "")
        guidance_text = ""
        if router_guidance:
            guidance_text = f"\nROUTER INSTRUCTIONS FOR THIS RESPONSE: {router_guidance}\n"
        
        # Dynamically add instructions if the agent is about to give up
        final_warning = ""

        is_final_attempt = current_iteration >= max_iterations
        if is_final_attempt:
            final_warning = SYNTHESIZER_FINAL_WARNING
        
            
        system_prompt = SYNTHESIZER_SYSTEM_PROMPT.format(
            query=query,
            guidance_text=guidance_text,
            context_string=context_string,
            final_warning=final_warning
        )

        # Tier 1 for best quality synthesis
        llm = llm_service.get_structured_primary_model(SynthesizerOutput)

        # Include recent messages for context awareness
        recent_messages = get_recent_messages(state.get("messages", []), last_k_turns=5)

        messages_to_send: List[BaseMessage] = [
            SystemMessage(content=system_prompt),
            *recent_messages,
            HumanMessage(content=query)
        ]

        try:
            result = await llm.ainvoke(messages_to_send)
        except asyncio.TimeoutError:
            logger.error(f"[Synthesizer] ❌ LLM generation timed out after {synthesizer_timeout} seconds.")
            error_text = "I apologize, but synthesizing this massive amount of data took too long and timed out. Could you please narrow down your question?"
            return Command(
                goto=AgentGraphNode.END_NODE,
                update={
                    "final_answer": error_text,
                    "is_complete": True,
                    "messages": [AIMessage(content=error_text, additional_kwargs={"execution_id": str(state.get("execution_id"))})]
                }
            )
        except Exception as e:
            logger.error(f"[Synthesizer] ❌ LLM Generation failed: {e}")
            error_text = "I apologize, but I encountered an error while formatting the synthesized information."
            return Command(
                goto=AgentGraphNode.END_NODE,
                update={
                    "final_answer": error_text,
                    "is_complete": True,
                    "messages": [AIMessage(content=error_text, additional_kwargs={"execution_id": str(state.get("execution_id"))})]
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
