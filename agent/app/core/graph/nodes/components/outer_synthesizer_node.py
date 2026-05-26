import asyncio
from typing import Literal
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.types import Command

from app.schemas.agent.synthesizer import SynthesizerOutput
from app.common.constants import StreamingTag
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.planner_state import PlanExecuteState
from app.core.prompts.outer_synthesizer_prompts import OUTER_SYNTHESIZER_SYSTEM_PROMPT
from app.services.llm.llm_service import LLMService
from app.utils.graph.context_utils import format_optimized_context

def make_outer_synthesizer_node(llm_service: LLMService):
    async def outer_synthesizer(state: PlanExecuteState) -> Command[Literal[AgentGraphNode.SUMMARIZER]]:
        logger.info("========== [Outer Synthesizer] Writing Terminal Response ==========")

        query = state["query"]
        past_steps = state.get("past_steps", [])

        # If the planner already computed a direct response (no research steps needed),
        # pass it through instead of calling LLM regenerating without workspace context.
        existing_answer = state.get("final_answer")
        if existing_answer and not past_steps:      # Distinct with Replanner output
            logger.info("[Outer Synthesizer] Passing through planner direct response.")
            return Command(
                goto=AgentGraphNode.SUMMARIZER,
                update={
                    "final_answer": existing_answer,
                    "messages": [AIMessage(content=existing_answer)]
                }
            )

        # 1. Workspace context so the LLM knows what datasets are available
        active_project = state.get("active_project")
        active_datasets = state.get("active_datasets", [])
        workspace_context = format_optimized_context(active_project, active_datasets)

        # 2. Format execution context (with truncation to prevent overflow)
        # We take the best results from the entire plan execution
        rag_results = state.get("rag_results", [])[:10]
        web_results = state.get("web_results", [])[:5]
        tool_results = state.get("tool_results", [])[-10:] 
        
        rag_context = "\n".join([f"- [Doc: {r.get('source_file')}] {r.get('content')[:1000]}..." for r in rag_results])
        web_context = "\n".join([f"- [{r.get('title')}] ({r.get('link')}): {r.get('snippet')}" for r in web_results])
        tool_context = "\n".join([f"- [{r.get('tool_name')}] Status: {r.get('status')}\nOutput: {r.get('output')[:1000]}..." for r in tool_results])

        # 3. Format the past steps into a clear evidence string
        steps_context = ""
        for step in past_steps:
            steps_context += f"OBJECTIVE: {step.summary}\nRESULT: {step.extracted_data}\n\n"

        prompt = OUTER_SYNTHESIZER_SYSTEM_PROMPT.format(
            query=query,
            past_steps=steps_context,
            workspace_context=workspace_context,
            rag_context=rag_context if rag_context else "No RAG data found.",
            web_context=web_context if web_context else "No web data found.",
            tool_context=tool_context if tool_context else "No tool data found."
        )
        
        # 2. Structured Model tagged for real-time JSON streaming
        # TODO: Tagging
        llm = llm_service.get_structured_primary_model(SynthesizerOutput).with_config(
            {"tags": [StreamingTag.STREAM_SYNTHESIZER]}
        )
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ]
        
        # 3. Final Invocation with Error Handling
        try:
            # Adding a reasonable timeout to prevent hanging the pipeline
            result: SynthesizerOutput = await llm.ainvoke(messages)
            final_answer = result.answer
        except asyncio.TimeoutError:
            logger.error("[Outer Synthesizer] LLM generation timed out.")
            final_answer = "I apologize, but synthesizing the final report took too long and timed out."
        except Exception as e:
            logger.error(f"[Outer Synthesizer] Final Synthesis failed: {e}")
            final_answer = "I apologize, but I encountered an error while formatting the final answer."
        
        # 4. Route to Summarizer
        return Command(
            goto=AgentGraphNode.SUMMARIZER, 
            update={
                "final_answer": final_answer,
                "messages": [AIMessage(content=final_answer)]
            }
        )
        
    return outer_synthesizer