# import time
# from typing import List, Literal
# from loguru import logger
# from langchain_core.messages import SystemMessage, HumanMessage
# from langgraph.graph import END
# from langgraph.types import Command
# from pydantic import BaseModel, Field

# from app.core.prompts.replanner_prompts import REPLANNER_HUMAN_PROMPT, REPLANNER_SYSTEM_PROMPT
# from app.utils.observability.tracing import tracing
# from app.configs.settings.settings import get_settings
# from app.common.constants import ObservationType, PlanStatus
# from app.core.graph.state.planner_state import AgentStepPlan, PlanExecuteState
# from app.core.graph.nodes.agent_graph_node import AgentGraphNode
# from app.services.llm.llm_service import LLMService

# class ReplanOutput(BaseModel):
#     is_complete: bool = Field(description="True if the user's ORIGINAL query is now fully answered.")
#     final_answer: str = Field(description="If complete, write the final, synthesized response to the user here.")
#     updated_plan: List[AgentStepPlan] = Field(description="If NOT complete, provide the remaining steps.")

# def make_replanner_node(llm_service: LLMService):
#     @tracing(observation_type=ObservationType.CHAIN)
#     async def replanner(state: PlanExecuteState) -> Command[
#         Literal[
#             AgentGraphNode.EXECUTOR,
#             AgentGraphNode.END_NODE
#         ]   
#     ]:
#         logger.info("🔄 [Replanner] Assessing progress...")
#         settings = get_settings()
#         query = state["query"]
#         past_steps = state.get("past_steps", [])
#         plan = state.get("plan", [])
#         iteration_count = state.get("iteration_count", 0)
#         max_planner_iteration = settings.REPLANNER_MAX_PLANNER_ITERATION

#         # Time-boxing: Prevent 504 Gateway Timeout (120s limit)
#         start_time = state.get("start_time", time.time())
#         elapsed_time = time.time() - start_time
#         if elapsed_time > 100: # 100s budget to allow for final synthesis
#             logger.warning(f"🕒 [Replanner] Time budget exceeded ({int(elapsed_time)}s). Forcing synthesis.")
#             return Command(
#                 goto=AgentGraphNode.END_NODE, 
#                 update={"final_answer": "I have completed as much research as possible within the time limit. Based on what I've found so far..."}
#             )

#         # Circuit Breaker: Max Iterations
#         if iteration_count >= max_planner_iteration:
#             logger.warning("🛑 [Replanner] Max iterations hit. Forcing exit.")
#             return Command(
#                 goto=AgentGraphNode.END_NODE, 
#                 update={"final_answer": "Task timed out after maximum steps."}
#             )

#         completed_text = "\n".join([f"- Step {obs.step_id} Result: {obs.summary}" for obs in past_steps])
#         pending_steps = [s for s in plan if s.status == PlanStatus.PENDING]

#         # Tier 3 (Tertiary - Flash Lite) for high-speed assessment
#         llm = llm_service.get_structured_tertiary_model(ReplanOutput)
        
#         result: ReplanOutput = await llm.ainvoke([
#             SystemMessage(content=REPLANNER_SYSTEM_PROMPT.format()), 
#             HumanMessage(content=REPLANNER_HUMAN_PROMPT.format(
#                 query=query,
#                 completed_text=completed_text,
#                 pending_steps=[s.description for s in pending_steps]
#             ))
#         ])

#         if result.is_complete:
#             logger.info("✅ [Replanner] Plan complete! Routing to END.")
#             return Command(
#                 goto=AgentGraphNode.END_NODE,
#                 update={
#                     "final_answer": result.final_answer,
#                     "iteration_count": iteration_count + 1
#                 }
#             )
#         else:
#             logger.info("⏳ [Replanner] More steps required. Routing to Executor.")
#             return Command(
#                 goto=AgentGraphNode.EXECUTOR,
#                 update={
#                     "plan": result.updated_plan,
#                     "iteration_count": iteration_count + 1
#                 }
#             )

#     return replanner