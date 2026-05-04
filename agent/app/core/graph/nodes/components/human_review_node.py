from typing import Any, Literal
from loguru import logger
from langgraph.types import Command, interrupt
from langchain_core.messages import HumanMessage

from app.utils.observability.tracing import tracing
from app.common.constants import ObservationType, InterruptAction, UserFeedbackAction
from app.core.graph.state.planner_state import PlanExecuteState, AgentStepPlan
from app.core.graph.nodes.agent_graph_node import AgentGraphNode

def make_human_review_node():
    @tracing(observation_type=ObservationType.CHAIN)
    async def human_review(state: PlanExecuteState) -> Command[
        Literal[AgentGraphNode.EXECUTOR, AgentGraphNode.PLANNER]
    ]:
        # 1. Pause for human approval using the plan already saved in state
        project = state.get("active_project") or {}

        p_name = project.get("project_name", "Default Project") if project else "Default Project"
        p_desc = project.get("description", "No description provided.") if project else ""
        decision: Any = interrupt({
            "action_required": InterruptAction.APPROVE_PLAN,
            "plan": [step.model_dump() for step in state.get("plan", [])],
            "query": state.get("query"),
            "project_context": f"{p_name} - {p_desc}"
        })

        # 2. Handle the decision returned when the graph is resumed
        if isinstance(decision, dict):
            
            # SCENARIO A: User typed a prompt to modify the plan
            if decision.get("action") == UserFeedbackAction.MODIFY and decision.get("feedback"):
                logger.info(f"User requested LLM modification: {decision.get('feedback')}")
                
                feedback_msg = HumanMessage(content=f"Please modify the plan based on this feedback: {decision.get('feedback')}")
                
                # Loop back to PLANNER to redraw the plan
                return Command(
                    goto=AgentGraphNode.PLANNER, 
                    update={"messages": [feedback_msg]} 
                )
                
            # SCENARIO B: User manually dragged/dropped or edited the JSON in the UI
            elif decision.get("action") == UserFeedbackAction.MODIFY and decision.get("modified_plan"):
                logger.info("User provided a manually edited plan. Proceeding to EXECUTOR.")
                final_steps = [AgentStepPlan(**s) if isinstance(s, dict) else s for s in decision["modified_plan"]]
                
                return Command(
                    goto=AgentGraphNode.EXECUTOR,
                    update={"plan": final_steps, "iteration_count": 0}
                )

        # SCENARIO C: User Approved (or default fallback)
        logger.info("Plan approved. Proceeding to EXECUTOR.")
        return Command(
            goto=AgentGraphNode.EXECUTOR,
            update={"iteration_count": 0}
        )

    return human_review