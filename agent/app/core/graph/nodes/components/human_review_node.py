from typing import Any, Literal
from loguru import logger
from langgraph.types import Command, interrupt
from langchain_core.messages import HumanMessage

from app.utils.observability.tracing import tracing
from app.common.constants import ObservationType, InterruptAction, PlanStatus, UserFeedbackAction
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
                logger.info("User provided a manually edited plan. Re-indexing and proceeding to EXECUTOR.")
                
                raw_plan = decision["modified_plan"]
                final_steps = []
                
                # Use enumerate to guarantee sequential step_ids starting at 1
                for index, step_data in enumerate(raw_plan, start=1):
                    if isinstance(step_data, dict):
                        # Force the step_id to match the current array index
                        step_data["step_id"] = index
                        # Ensure status resets to pending just in case the UI sent a completed step
                        step_data["status"] = PlanStatus.PENDING 
                        final_steps.append(AgentStepPlan(**step_data))
                    
                    elif isinstance(step_data, AgentStepPlan):
                        step_data.step_id = index
                        step_data.status = PlanStatus.PENDING
                        final_steps.append(step_data)

                return Command(
                    goto=AgentGraphNode.EXECUTOR,
                    update={"plan": final_steps}
                )

        # SCENARIO C: User Approved (or default fallback)
        logger.info("Plan approved. Proceeding to EXECUTOR.")
        return Command(
            goto=AgentGraphNode.EXECUTOR,
            update={}
        )

    return human_review