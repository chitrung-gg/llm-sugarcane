from typing import Any, Dict, List, Literal, Optional
from loguru import logger
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.core.prompts.planner_prompts import PLANNER_HUMAN_PROMPT, PLANNER_SYSTEM_PROMPT
from app.utils.observability.tracing import tracing
from app.common.constants import ObservationType, PlanStatus, InterruptAction, UserFeedbackAction
from app.core.graph.state.planner_state import AgentStepPlan, PlanExecuteState
from app.schemas.agent.planner import PlanOutput
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.services.llm.llm_service import LLMService
from app.utils.graph.context_utils import get_recent_messages, format_optimized_workspace

# Notice we now accept `agent_capabilities: List[str]` instead of `available_tools`
def make_planner_node(llm_service: LLMService, agent_capabilities: List[str]):
    @tracing(observation_type=ObservationType.CHAIN)
    async def planner(state: PlanExecuteState) -> Command[
        Literal[AgentGraphNode.HUMAN_REVIEW, AgentGraphNode.SUMMARIZER]
    ]:
        logger.info("🧠 [Planner] Drafting research plan...")

        query = state["query"]
        project = state.get("active_project")
        active_datasets = state.get("active_datasets", [])
        system_datasets = state.get("system_datasets", [])

        # 1. Block A: Workspace Context
        workspace_context = format_optimized_workspace(project, active_datasets, system_datasets)
        p_name = project.get("project_name", "Default Project") if project else "Default Project"
        p_desc = project.get("description", "No description provided.") if project else ""

        # 2. Block B: Dynamic Agent Capabilities (Passed down from graph.py)
        agent_capabilities_str = "\n".join([f"{i+1}. {cap}" for i, cap in enumerate(agent_capabilities)])

        # 3. Block C: Recent Message History for Coreference Resolution
        recent_messages = get_recent_messages(state.get("messages", []), n=5)
        if recent_messages and recent_messages[-1].content == query:
            recent_messages = recent_messages[:-1]
            
        chat_history_str = "\n".join(
            [f"{msg.type.capitalize()}: {msg.content}" for msg in recent_messages]
        ) if recent_messages else "No prior context."

        # 4. Format System Prompt
        system_msg = SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(
            project_name=p_name,
            project_description=p_desc,
            datasets=workspace_context,
            agent_capabilities_str=agent_capabilities_str,
            chat_history_str=chat_history_str
        ))

        # 5. The Current Task
        task_msg = HumanMessage(content=PLANNER_HUMAN_PROMPT.format(query=f"### NEW REQUEST ###\n{query}"))

        messages: List[BaseMessage] = [system_msg] + recent_messages + [task_msg]

        # 6. Execute Model
        llm = llm_service.get_structured_primary_model(PlanOutput)
        try:
            result: PlanOutput = await llm.ainvoke(messages)
        except Exception as e:
            logger.error(f"[Planner] Failed to generate plan: {e}")
            raise e
        
        # 7. Route Output
        if not result.steps:
            logger.info("[Planner] No steps generated. Routing directly to Summarizer.")
            final_text = result.direct_response or "I don't think any specific research steps are needed."
            return Command(
                goto=AgentGraphNode.SUMMARIZER,
                update={"plan": [], "final_answer": final_text, "messages": [AIMessage(content=final_text)]}
            )

        plan_preview = "\n".join([f"{s.step_id}. {s.description}" for s in result.steps])
        announcement = f"I've drafted a research plan for you:\n\n{plan_preview}\n\nPlease review and approve it to proceed."
        
        return Command(
            goto=AgentGraphNode.HUMAN_REVIEW,
            update={
                "plan": result.steps, 
                "iteration_count": 0,
                "past_steps": [], 
                "messages": [AIMessage(content=announcement)]
            }
        )

    return planner