from typing import List, Literal
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.core.prompts.planner_prompts import PLANNER_HUMAN_PROMPT, PLANNER_SYSTEM_PROMPT
from app.utils.observability.tracing import tracing
from app.common.constants import ObservationType
from app.core.graph.nodes.agent_planner import AgentStepPlan, PlanExecuteState
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.services.llm.llm_service import LLMService

class PlanOutput(BaseModel):
    steps: List[AgentStepPlan] = Field(description="The sequential steps to execute the research plan. Maximum 5 steps.")

def make_planner_node(llm_service: LLMService):
    @tracing(observation_type=ObservationType.CHAIN)
    async def planner(state: PlanExecuteState) -> Command[Literal[AgentGraphNode.EXECUTOR]]:
        logger.info("🧠 [Planner] Drafting research plan...")
        query = state["query"]

        llm = llm_service.get_structured_primary_model(PlanOutput)
        
        try:
            result: PlanOutput = await llm.ainvoke([
                SystemMessage(content=PLANNER_SYSTEM_PROMPT.format()), 
                HumanMessage(content=PLANNER_HUMAN_PROMPT.format(query=query))
            ])
            
            logger.debug(f"[Planner] Generated {len(result.steps)} steps.")
            
            return Command(
                goto=AgentGraphNode.EXECUTOR,
                update={
                    "plan": result.steps,
                    "iteration_count": 0
                }
            )
        except Exception as e:
            logger.error(f"[Planner] Failed to generate plan: {e}")
            raise e

    return planner