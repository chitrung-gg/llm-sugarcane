import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Any, List, cast
import uuid

from app.common.constants import UserFeedbackAction
from app.configs.loggings.loggings import setup_logging
from app.configs.settings.settings import get_settings

os.environ["DEEPEVAL_TIMEOUT"] = "6000"
setup_logging()

from deepeval import evaluate
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import BaseMetric, GEval
from deepeval.evaluate import AsyncConfig, DisplayConfig
from deepeval.dataset import EvaluationDataset
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from loguru import logger

from evaluation.llm_judge import GoogleGeminiJudge

def extract_tool_names_from_state(state: dict) -> List[str]:
    """
    Parses the LangGraph state directly to extract tool names from the hidden trace arrays.
    """
    executed_tools = []
    
    # Check tool_results array
    for tr in state.get("tool_results", []):
        if isinstance(tr, dict) and "tool_name" in tr:
            executed_tools.append(tr.get("tool_name"))
            
    # Check web_results array
    for wr in state.get("web_results", []):
        if isinstance(wr, dict) and "tool_name" in wr:
            executed_tools.append(wr.get("tool_name"))
            
    return list(set(executed_tools)) # Return unique names only

async def run_geval_evaluations(dataset_path: str):
    from app.configs.storage.databases import (
        genome_connection_pool, 
        langgraph_connection_pool, 
        userdata_connection_pool
    )
    from app.core.app_container import get_container
    
    logger.info("🔌 Opening PostgreSQL connection pools...")
    await genome_connection_pool.open()
    await langgraph_connection_pool.open()
    await userdata_connection_pool.open()

    try:
        settings = get_settings()
        container = get_container()
        await container.initialize()
        agent_service = container.agent_service

        # --- Instantiate Judges ---
        task_judge = GoogleGeminiJudge(model_name=settings.GEMINI_PRIMARY_MODEL)
        efficiency_judge = GoogleGeminiJudge(model_name=settings.GEMINI_TERTIARY_MODEL)

        # --- Define GEval Metrics ---
        plan_quality_geval = GEval(
            name="Plan Quality",
            evaluation_steps=[
                "Review the user's 'input' query.",
                "Extract the 'AGENT PLAN' from the 'actual output'.",
                "Evaluate if the plan logically breaks down the bioinformatics problem.",
                "Check if the plan proposes using the correct biological databases or tools (e.g., proposing NCBI for genomes, Neo4j for traits).",
                "Penalize if the plan is overly vague, hallucinates tools that don't exist, or misses critical steps required to answer the query.",
                "Score 1.0 for a perfect, logical, sequential scientific research plan."
            ],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            model=task_judge,
            threshold=0.7
        )

        step_efficiency_geval = GEval(
            name="Step Efficiency",
            evaluation_steps=[
                "Extract the list of 'Tools Executed' from the 'actual output'.",
                "Evaluate if the number and choice of tools were optimal for the 'input' query.",
                "Penalize heavily if the agent called the same tool multiple times unnecessarily.",
                "Penalize if the agent got stuck in a loop or used a long sequence of tools when a single tool would have sufficed."
            ],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            model=efficiency_judge,
            threshold=0.7
        )

        plan_adherence_geval = GEval(
            name="Plan Adherence",
            evaluation_steps=[
                "Extract the 'AGENT PLAN' and the 'TOOLS EXECUTED' from the 'actual output'.",
                "Compare the tools that were actually executed against the steps proposed in the plan.",
                "Did the agent actually follow its own instructions? Or did it go off-script and execute random tools?",
                "Penalize the score if the agent skipped planned steps without a valid reason.",
                "Score 1.0 if the executed tools perfectly align with the intended plan."
            ],
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            model=efficiency_judge,
            threshold=0.7
        )

        coherence_geval = GEval(
            name="Coherence",
            evaluation_steps=[
                "Focus purely on the 'Final Answer' section of the 'actual output', ignoring the JSON tool trace.",
                "Check for fluency: ensure the text reads smoothly with correct grammar and syntax.",
                "Check for clarity and logical progression of ideas.",
                "Penalize repetitiveness, redundancy, or unnecessary filler words.",
                "Penalize disjointed sentences or abrupt topic changes."
            ],
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            model=efficiency_judge,
            threshold=0.7
        )

        tonality_geval = GEval(
            name="Tonality",
            evaluation_steps=[
                "Focus purely on the 'Final Answer' section of the 'actual output', ignoring the JSON tool trace.",
                "Assess the level of professionalism and scientific expertise conveyed.",
                "Check if the tone is suitable for a bioinformatics researcher or agronomist.",
                "Penalize overly casual language, inappropriate emojis, or lack of directness.",
                "Reward clear, objective, and academic communication styles."
            ],
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            model=efficiency_judge,
            threshold=0.7
        )

        metrics: List[BaseMetric] = [
            plan_quality_geval,
            plan_adherence_geval,
            step_efficiency_geval,
            coherence_geval,
            tonality_geval
        ]

        # --- LOAD DATASET DYNAMICALLY ---
        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"Dataset not found at: {dataset_path}")
            
        logger.info(f"Loading GEval dataset from {dataset_path}...")
        with open(dataset_path, "r", encoding="utf-8") as f:
            test_data = json.load(f)

        current_file_name = os.path.splitext(os.path.basename(__file__))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        env_base_folder = os.getenv("DEEPEVAL_RESULTS_FOLDER", "./evaluation")
        base_eval_folder = os.path.abspath(env_base_folder)

        folder_name = f"{current_file_name}_{timestamp}"
        run_folder = os.path.join(base_eval_folder, folder_name)
        os.makedirs(run_folder, exist_ok=True)

        logger.info(f"Starting GEval evaluation run. Saving results to: {run_folder}")
        test_cases = []

        for item in test_data:
            query = item["input"]
            expected_output = item.get("expected_output", "")
            
            config = cast(RunnableConfig, {
                "configurable": {"thread_id": str(uuid.uuid4())}
            })
            
            # --- Run Agent Planner ---
            initial_state = {
                "query": query,
                "messages": [HumanMessage(content=query)],
                "active_datasets": [],
                "iteration_count": 0,
            }
            
            # 1. Run until it hits the Human Approval breakpoint
            suspended_state = await asyncio.wait_for(
                agent_service.graph.ainvoke(initial_state, config=config),
                timeout=1000 
            )
            
            # 2. Check if the graph suspended and trigger Executor
            current_thread_state = await agent_service.graph.aget_state(config)
            
            if current_thread_state.next:
                logger.info(f"Test case: '{query}' -> Graph suspended. Simulating Human Approval...")
                mock_approval = Command(resume={"action": UserFeedbackAction.APPROVE})
                final_state = await asyncio.wait_for(
                    agent_service.graph.ainvoke(mock_approval, config=config),
                    timeout=1000
                )
            else:
                logger.info(f"Test case: '{query}' -> Graph did not suspend. Proceeding.")
                final_state = suspended_state
            
            # 1. Get Tool Names for Efficiency Metric (Using Robust State Extraction)
            actual_tool_names = extract_tool_names_from_state(final_state)
            
            # Robust final answer extraction
            final_answer = final_state.get('final_answer', '')
            if not final_answer:
                for msg in reversed(final_state.get("messages", [])):
                    if getattr(msg, "type", "") == "ai" and msg.content:
                        final_answer = str(msg.content)
                        break

            raw_plan = final_state.get("plan", [])
            plan_text = ""
            for step in raw_plan:
                # Format it so the Judge can easily read it
                plan_text += f"Step {getattr(step, 'step_id', '?')}: {getattr(step, 'description', '')}\n"
            
            if not plan_text:
                plan_text = "No plan was generated."

            # --- Inject everything into the Combined Output ---
            combined_actual_output = (
                f"=== AGENT PLAN ===\n{plan_text}\n\n"
                f"=== TOOLS EXECUTED ===\n{actual_tool_names}\n\n"
                f"=== FINAL ANSWER ===\n{final_answer}"
            )

            # 2. AGGREGATE ALL CONTEXT FOR RAG METRICS
            actual_retrieval_context = []
            
            actual_retrieval_context.extend(
                [str(res.get("content", res)) for res in final_state.get("rag_results", [])]
            )
            actual_retrieval_context.extend(
                [str(res.get("output", res)) for res in final_state.get("tool_results", [])]
            )
            actual_retrieval_context.extend(
                [str(res.get("content", res)) for res in final_state.get("web_results", [])]
            )
            
            # Fallback for empty context
            if not actual_retrieval_context:
                actual_retrieval_context = ["No context was retrieved by the agent."]

            # 3. Build TestCase
            test_case = LLMTestCase(
                input=query,
                actual_output=combined_actual_output, 
                expected_output=expected_output,
                retrieval_context=actual_retrieval_context 
            )
            test_cases.append(test_case)

        # --- Construct Dataset and Evaluate ---
        dataset = EvaluationDataset()
        for tc in test_cases:
            dataset.add_test_case(tc)

        dataset.save_as(file_type="json", directory=run_folder, include_test_cases=True)
        
        evaluate(
            test_cases=dataset.test_cases,
            metrics=metrics,
            display_config=DisplayConfig(results_folder=run_folder),
            async_config=AsyncConfig(max_concurrent=1)
        )
        
    finally:
        logger.info("🛑 Closing PostgreSQL connection pools...")
        await genome_connection_pool.close()
        await langgraph_connection_pool.close()
        await userdata_connection_pool.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Custom GEval Agent Evaluations.")
    parser.add_argument(
        "--dataset", 
        type=str, 
        required=True, 
        help="Path to the GEval JSON dataset file."
    )
    args = parser.parse_args()
    asyncio.run(run_geval_evaluations(dataset_path=args.dataset))