import asyncio
from datetime import datetime
import os
from typing import Any, List, cast
import uuid

from app.configs.loggings.loggings import setup_logging
from app.configs.settings.settings import get_settings

os.environ["DEEPEVAL_TIMEOUT"] = "600"
setup_logging()

from deepeval import evaluate
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import TaskCompletionMetric, ToolCorrectnessMetric, StepEfficiencyMetric
from deepeval.evaluate import AsyncConfig, DisplayConfig
from deepeval.dataset import EvaluationDataset
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from evaluation.llm_judge import GoogleGeminiJudge

def extract_tool_calls_from_state(messages: List[Any]) -> List[ToolCall]:
    """
    Parses LangChain AIMessages to extract tool execution histories 
    and converts them into DeepEval ToolCall objects.
    """
    deepeval_tools = []
    
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                deepeval_tools.append(
                    ToolCall(
                        name=tc.get("name", "unknown_tool"),
                        # description="Description omitted for extraction", # Optional in DeepEval
                        input_parameters=tc.get("args", {})
                    )
                )
    return deepeval_tools

async def run_agentic_evaluations():
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
        tool_judge = GoogleGeminiJudge(model_name=settings.gemini_primary_model)
        task_judge = GoogleGeminiJudge(model_name=settings.gemini_secondary_model)
        efficiency_judge = GoogleGeminiJudge(model_name=settings.gemini_tertiary_model)

        # ==========================================
        # CUSTOM GEVAL METRICS (OFFLINE SAFE)
        # ==========================================
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCaseParams

        # --- Create Offline GEval Metrics ---
        task_completion_geval = GEval(
            name="Task Completion",
            criteria="Determine whether the agent successfully completed the user's requested task based purely on the tools it decided to call and its final output.",
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT], # <-- Fixed Enum
            model=task_judge,
            threshold=0.7,
            async_mode=False
        )

        step_efficiency_geval = GEval(
            name="Step Efficiency",
            criteria="Evaluate the efficiency of the agent's tool usage. Penalize the agent if it called the same tool multiple times unnecessarily, got stuck in a loop, or used a long sequence of tools when a single tool would have sufficed. The tools used are listed in the actual output.",
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT], # <-- Fixed Enum
            model=efficiency_judge,
            threshold=0.7,
            async_mode=False
        )

        # --- Define Agentic Metrics ---
        metrics = [
            ToolCorrectnessMetric(
                threshold=0.7, 
                model=tool_judge,
                # assess_tool_args=True  <-- DELETED THIS LINE
                async_mode=False
            ),
            task_completion_geval,
            step_efficiency_geval
        ]

        # --- Define Agent-Specific Test Queries ---
        test_data = [
            {
                "input": "Search NCBI for sugarcane genome assembly GCA_038087645.1 and summarize its stats.",
                "expected_tools": [
                    ToolCall(
                        name="search_ncbi_genome", 
                        input_parameters={"accession": "GCA_038087645.1"}
                    )
                ]
            },
        ]

        current_file_name = os.path.splitext(os.path.basename(__file__))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        env_base_folder = os.getenv("DEEPEVAL_RESULTS_FOLDER", "./evaluation")
        base_eval_folder = os.path.abspath(env_base_folder)

        folder_name = f"{current_file_name}_{timestamp}"
        run_folder = os.path.join(base_eval_folder, folder_name)
        os.makedirs(run_folder, exist_ok=True)

        logger.info(f"Starting Agentic evaluation run. Saving results to: {run_folder}")
        test_cases = []

        for item in test_data:
            query = item["input"]
            expected_tool_names = item["expected_tools"]
            
            config = cast(RunnableConfig, {
                "configurable": {"thread_id": str(uuid.uuid4())}
            })
            
            # --- Run Agent ---
            initial_state = {
                "query": query,
                "messages": [HumanMessage(content=query)],
                "active_datasets": [],
                "iteration_count": 0,
            }
            final_state = await asyncio.wait_for(
                agent_service.graph.ainvoke(initial_state, config=config),
                timeout=1000 
            )
            
            actual_tool_calls = extract_tool_calls_from_state(final_state.get("messages", []))
            
            # --- NEW: Format a combined output for the GEval Judges ---
            actual_tool_names = [tc.name for tc in actual_tool_calls]
            combined_actual_output = (
                f"Tools Executed: {actual_tool_names}\n\n"
                f"Final Answer: {final_state.get('final_answer', '')}"
            )

            # --- Build TestCase ---
            test_case = LLMTestCase(
                input=query,
                actual_output=combined_actual_output, # GEval reads this combined string
                tools_called=actual_tool_calls,       # ToolCorrectnessMetric reads this
                expected_tools=expected_tool_names    # ToolCorrectnessMetric reads this
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
    asyncio.run(run_agentic_evaluations())