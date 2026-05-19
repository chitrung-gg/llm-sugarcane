from typing import List, Literal
from loguru import logger
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage
from langgraph.types import Command

from app.core.prompts.planner_prompts import PLANNER_HUMAN_PROMPT, PLANNER_SYSTEM_PROMPT
from app.utils.observability.tracing import tracing
from app.common.constants import ObservationType, StreamingTag
from app.core.graph.state.planner_state import PlanExecuteState
from app.schemas.agent.planner import PlanOutput
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.services.llm.llm_service import LLMService
from app.utils.graph.context_utils import format_optimized_context, get_recent_messages

def make_planner_node(llm_service: LLMService, agent_capabilities: List[str]):
    @tracing(observation_type=ObservationType.CHAIN)
    async def planner(state: PlanExecuteState) -> Command[
        Literal[AgentGraphNode.HUMAN_REVIEW, AgentGraphNode.OUTER_SYNTHESIZER]
    ]:
        logger.info("🧠 [Planner] Drafting research plan...")

        query = state["query"]
        
        project = state.get("active_project")
        active_datasets = state.get("active_datasets", [])

        # 2. Format it into a string
        active_project_context = format_optimized_context(project, active_datasets)
 
        # Formatting Agent Capabilities
        agent_capabilities_str = "\n".join([f"{i+1}. {cap}" for i, cap in enumerate(agent_capabilities)])

        # Formatting Recent Messages
        raw_recent_messages = get_recent_messages(state.get("messages", []), last_k_turns=3)
        recent_messages = [
            msg for msg in raw_recent_messages 
            if not msg.additional_kwargs.get("is_thought")
        ]

        # Don't add latest query into recent_messages
        if recent_messages and recent_messages[-1].content == query:
            recent_messages = recent_messages[:-1]
            
        chat_history_str = "\n".join(
            [f"{msg.type.capitalize()}: {msg.content}" for msg in recent_messages]
        ) if recent_messages else "No prior context."

        # Formatting Past Steps
        past_steps = state.get("past_steps", [])
        if past_steps:
            formatted_steps = []
            for s in past_steps:
                step_summary = s.summary
                formatted_steps.append(f"- {step_summary}")
            past_steps_str = "\n".join(formatted_steps)
        else:
            past_steps_str = "No background research executed yet."
            
        conv_summary = state.get("summary", "No summary available.")

        # 3. Format the Prompt using `active_datasets`
        system_msg = SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(
            active_project_context=active_project_context,
            agent_capabilities_str=agent_capabilities_str,
            chat_history_str=chat_history_str,
            past_steps_str=past_steps_str, 
            conv_summary=conv_summary            
        ))

        task_msg = HumanMessage(content=PLANNER_HUMAN_PROMPT.format(query=f"### NEW REQUEST ###\n{query}"))
        messages: List[BaseMessage] = [system_msg] + recent_messages + [task_msg]

        # Execute Model
        llm = llm_service.get_structured_primary_model(PlanOutput).with_config(
            {"tags": [StreamingTag.STREAM_PLANNER]}
        )
        
        try:
            result: PlanOutput = await llm.ainvoke(messages)
        except Exception as e:
            logger.error(f"[Planner] Failed to generate plan: {e}")
            raise e
        
        # Route Output Based on Direct Responses vs Multi-Step Plans
        if not result.steps:
            logger.info("[Planner] No steps generated. Routing directly to Synthesizer.")
            
            final_text = result.direct_response or "I reviewed your request, but no specific research steps are needed right now."
            
            return Command(
                goto=AgentGraphNode.OUTER_SYNTHESIZER,
                update={
                    "plan": [], 
                    "final_answer": final_text, 
                    "messages": [AIMessage(content=final_text)]
                }
            )

        # Standard Multi-Step Routing
        plan_preview = "\n".join([f"{s.step_id}. {s.description}" for s in result.steps])
        announcement = f"I've drafted a research plan for you:\n\n{plan_preview}\n\nPlease review and approve it to proceed."
        
        return Command(
            goto=AgentGraphNode.HUMAN_REVIEW,
            update={
                "plan": result.steps,
                "past_steps": [], 
                "messages": [AIMessage(content=announcement, additional_kwargs={"is_thought": True})]
            }
        )

    return planner