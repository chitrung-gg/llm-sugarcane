from typing import Any, Dict, List, Literal, Optional
from loguru import logger
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.core.prompts.planner_prompts import PLANNER_HUMAN_PROMPT, PLANNER_SYSTEM_PROMPT
from app.utils.observability.tracing import tracing
from app.common.constants import ObservationType, PlanStatus, InterruptAction, UserFeedbackAction
from app.core.graph.state.planner_state import AgentStepPlan, PlanExecuteState
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.services.llm.llm_service import LLMService

class PlanOutput(BaseModel):
    scratchpad: str = Field(description="Reasoning on validity, logic, and file availability.")
    direct_response: Optional[str] = Field(None, description="If no steps are needed, write the direct, helpful, conversational answer to the user here.")
    estimated_steps: int = Field(description="The total number of steps in the proposed plan.")
    steps: List[AgentStepPlan] = Field(default_factory=list, description="The sequential steps to execute the research plan. Maximum 5 steps.")

def make_planner_node(llm_service: LLMService):
    @tracing(observation_type=ObservationType.CHAIN)
    async def planner(state: PlanExecuteState) -> Command[
        Literal[AgentGraphNode.HUMAN_REVIEW, AgentGraphNode.SUMMARIZER]
    ]:
        logger.info("🧠 [Planner] Drafting research plan...")

        # 1. Extract context
        query = state["query"]
        project = state.get("active_project")
        datasets = state.get("active_datasets", [])

        # Format Project Info
        p_name = project.get("project_name", "Default Project") if project else "Default Project"
        p_desc = project.get("description", "No description provided.") if project else ""

        # 2. Format Datasets
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
        
        # Add historical messages BUT exclude the current/latest query 
        # (The latest query is always at the end of state["messages"])
        if state.get("messages") and len(state["messages"]) > 1:
            messages.extend(state["messages"][:-1])
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

        # 4. Handle 0-step cases (Greetings, clarification requests, etc.)
        if not result.steps:
            logger.info("[Planner] No steps generated. Routing directly to Summarizer.")

            final_text = result.direct_response or "I don't think any specific research steps are needed for this. How else can I help you today?"

            return Command(
                goto=AgentGraphNode.SUMMARIZER,
                update={
                    "plan": [],
                    "final_answer": final_text,
                    "messages": [AIMessage(content=final_text)]
                }
            )

        # 5. Route to Human Review (Save draft to state)
        return Command(
            goto=AgentGraphNode.HUMAN_REVIEW,
            update={
                "plan": result.steps, 
                "iteration_count": 0,
                "past_steps": [] # Reset execution history for the new plan
            }
        )

    return planner