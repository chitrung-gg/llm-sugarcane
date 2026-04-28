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
        # efficiency_judge = GoogleGeminiJudge(model_name=settings.gemini_tertiary_model)

        # --- Define Agentic Metrics ---
        metrics = [
            ToolCorrectnessMetric(
                threshold=0.7, 
                model=tool_judge,
                async_mode=False
            ),
            TaskCompletionMetric(
                threshold=0.7, 
                model=task_judge, 
                async_mode=False
            ),
            # StepEfficiencyMetric(
            #     threshold=0.7,
            #     model=efficiency_judge,
            #     async_mode=False
            # )
        ]

        # --- Define Agent-Specific Test Queries ---
        # Notice these are action-oriented, not just factual lookups.
        test_data = [
            {
                "input": "Search NCBI for sugarcane genome assembly GCA_038087645.1 and summarize its stats.",
                "expected_tools": [
                    ToolCall(
                        name="search_ncbi_genome", 
                        input_parameters={"accession": "GCA_038087645.1"} # Enforce exact extraction!
                    )
                ]
            },
            # {
            #     "input": "Find which genes are responsible for sucrose content in Saccharum according to literature.",
            #     "expected_tools": [
            #         ToolCall(
            #             name="search_literature_for_traits",
            #             input_parameters={
            #                 "organism": "Saccharum",
            #                 "primary_concept": "sucrose content"
            #             }
            #         )
            #     ]
            # },
            # {
            #     "input": "Compare the sucrose-related genes across all available sugarcane varieties.",
            #     "expected_tools": [
            #         # Step 1: The agent MUST figure out what the available IDs are first
            #         ToolCall(
            #             name="list_genome_files" ,
            #             input_parameters={

            #             }
            #         ),
            #         # Step 2: The agent passes the IDs and the exact keyword to the search tool
            #         ToolCall(
            #             name="cross_variety_search",
            #             input_parameters={
            #                 "keyword": "sucrose"
            #                 # Note: We deliberately leave out the "ids" parameter here.
            #                 # Because the IDs are dynamically fetched in Step 1 (e.g., "1,2,3,4"), 
            #                 # we cannot hardcode them in the test. DeepEval will still verify 
            #                 # that the "keyword" was correctly extracted!
            #             }
            #         )
            #     ]
            # },
        ]

        current_file_name = os.path.splitext(os.path.basename(__file__))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        env_base_folder = os.getenv("DEEPEVAL_RESULTS_FOLDER", "./evaluation")
        base_eval_folder = os.path.abspath(env_base_folder)

        # We don't sweep temperatures for Agent testing as often, 0.0 is best for tool calling
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
                timeout=1000 # 2 minute max per test case
            )
            
            # --- Extract LangGraph Tool Calls ---
            # Parses the state to see what the agent actually decided to do
            actual_tool_calls = extract_tool_calls_from_state(final_state.get("messages", []))
            

            # --- Build TestCase ---
            test_case = LLMTestCase(
                input=query,
                actual_output=str(final_state.get("final_answer", "")),
                tools_called=actual_tool_calls,
                expected_tools=expected_tool_names
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