from typing import Any, Dict, List, Literal
from loguru import logger
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.core.prompts.planner_prompts import PLANNER_HUMAN_PROMPT, PLANNER_SYSTEM_PROMPT
from app.utils.observability.tracing import tracing
from app.common.constants import ObservationType, PlanStatus, InterruptAction, UserFeedbackAction
from app.core.graph.state.planner_state import AgentStepPlan, PlanExecuteState
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.services.llm.llm_service import LLMService

class PlanOutput(BaseModel):
    steps: List[AgentStepPlan] = Field(description="The sequential steps to execute the research plan. Maximum 5 steps.")

def make_planner_node(llm_service: LLMService):
    @tracing(observation_type=ObservationType.CHAIN)
    async def planner(state: PlanExecuteState) -> Command[
        Literal[AgentGraphNode.EXECUTOR, AgentGraphNode.PLANNER]
    ]:
        logger.info("🧠 [Planner] Drafting research plan...")

        # 1. Skip plan generation if an approved plan already exists in state
        if state.get("plan"):
            logger.info("✅ [Planner] Plan already exists, proceeding to executor.")
            return Command(goto=AgentGraphNode.EXECUTOR)

        # 2. Extract Rich Context from TypedDicts
        query = state["query"]
        project = state.get("active_project")
        datasets = state.get("active_datasets", [])

        # Format Project Info
        p_name = project.get("project_name", "Default Project") if project else "Default Project"
        p_desc = project.get("description", "No description provided.") if project else ""

        # Format Dataset/File hierarchy for the Prompt
        dataset_lines = []
        for ds in datasets:
            ds_name = ds.get("dataset_name")
            source = ds.get("source")
            
            # Extract filenames by category
            genomic = [f["file_name"] for f in ds.get("genomic_files", [])]
            knowledge = [f["file_name"] for f in ds.get("knowledge_files", [])]
            
            lines = [f"- Dataset: {ds_name} (Source: {source})"]
            if genomic:
                lines.append(f"  * Genomic Files: {', '.join(genomic)}")
            if knowledge:
                lines.append(f"  * Knowledge Files: {', '.join(knowledge)}")
            
            dataset_lines.append("\n".join(lines))
        
        dataset_context = "\n".join(dataset_lines) if dataset_lines else "No datasets attached."

        # 3. Prepare Messages (Including Conversation History)
        llm = llm_service.get_structured_primary_model(PlanOutput)

        # We include previous messages so the Planner has full conversation context
        messages: List[BaseMessage] = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(
                project_name=p_name,
                project_description=p_desc,
                datasets=dataset_context
            ))
        ]
        
        # Add historical messages (Human/AI turns)
        if state.get("messages"):
            messages.extend(state["messages"])
        else:
            # Fallback if messages list is empty
            messages.append(HumanMessage(content=PLANNER_HUMAN_PROMPT.format(query=query)))

        try:
            result: PlanOutput = await llm.ainvoke(messages)
        except Exception as e:
            logger.error(f"[Planner] Failed to generate plan: {e}")
            raise e
        
        for i, step in enumerate(result.steps, 1):
            logger.debug(
                f"[Planner] Step {i}: {step.model_dump_json(indent=2)}"
            )

        # 4. Human-in-the-loop Interrupt
        decision: Any = interrupt({
            "action_required": InterruptAction.APPROVE_PLAN,
            "plan": [step.model_dump() for step in result.steps],
            "query": query
        })

        # 5. Handle Resumption Logic
        if isinstance(decision, dict):
            
            # 5.1. User typed a prompt to modify the plan (LLM needs to replan)
            if decision.get("action") == UserFeedbackAction.MODIFY and decision.get("feedback"):
                logger.info("User requested LLM modification. Looping back to PLANNER.")
                
                feedback_msg = HumanMessage(content=f"Please modify the plan based on this feedback: {decision.get('feedback')}")
                
                return Command(
                    goto=AgentGraphNode.PLANNER,
                    update={"messages": [feedback_msg]}
                )
                
            # 5.2. User manually dragged/dropped or edited the JSON in the UI
            elif decision.get("action") == UserFeedbackAction.MODIFY and decision.get("modified_plan"):
                logger.info("User provided a manually edited plan. Proceeding to EXECUTOR.")
                final_steps = [AgentStepPlan(**s) if isinstance(s, dict) else s for s in decision["modified_plan"]]
                
                return Command(
                    goto=AgentGraphNode.EXECUTOR,
                    update={"plan": final_steps, "iteration_count": 0}
                )

        # 5.3 User clicked "Approve" (or default fallback)
        logger.info("Plan approved. Proceeding to EXECUTOR.")
        return Command(
            goto=AgentGraphNode.EXECUTOR,
            update={"plan": result.steps, "iteration_count": 0}
        )

    return planner