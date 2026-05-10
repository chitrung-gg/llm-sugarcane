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

def make_outer_synthesizer_node(llm_service: LLMService):
    async def outer_synthesizer(state: PlanExecuteState) -> Command[Literal[AgentGraphNode.END_NODE]]:
        logger.info("========== [Outer Synthesizer] Writing Terminal Response ==========")
        
        query = state["query"]
        past_steps = state.get("past_steps", [])
        
        # 1. Format the past steps into a clear evidence string
        steps_context = ""
        for step in past_steps:
            steps_context += f"OBJECTIVE: {step.summary}\nRESULT: {step.extracted_data}\n\n"
            
        prompt = OUTER_SYNTHESIZER_SYSTEM_PROMPT.format(
            query=query,
            past_steps=steps_context
        )
        
        # 2. Structured Model tagged for real-time JSON streaming
        llm = llm_service.get_structured_primary_model(SynthesizerOutput).with_config(
            {"tags": [StreamingTag.STREAM_SYNTHESIZER]}
        )
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ]
        
        # 3. Final Invocation
        result = await llm.ainvoke(messages)
        
        # 4. Force Termination (No Replanning)
        # We ignore result.is_complete for routing and always go to END.
        return Command(
            goto=AgentGraphNode.END_NODE, 
            update={
                "final_answer": result.answer,
                "messages": [AIMessage(content=result.answer)]
            }
        )
        
    return outer_synthesizer