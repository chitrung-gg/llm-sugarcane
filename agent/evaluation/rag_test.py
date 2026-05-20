import argparse
import json
from typing import Any, cast
import os
from datetime import datetime
import uuid
from dotenv import load_dotenv
from loguru import logger
import asyncio
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage

from evaluation.llm_judge import GoogleGeminiJudge
from app.configs.loggings.loggings import setup_logging
from app.configs.settings.settings import get_settings

os.environ["DEEPEVAL_TIMEOUT"] = "6000"
os.environ["DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE"] = "600"
setup_logging()

from deepeval import assert_test, evaluate
from deepeval.evaluate import AsyncConfig, DisplayConfig
from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase
from deepeval.metrics import ContextualPrecisionMetric, ContextualRecallMetric, FaithfulnessMetric, AnswerRelevancyMetric, ContextualRelevancyMetric

# env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
# load_dotenv(dotenv_path=env_path, override=True)
    
async def run_rag_evaluations(dataset_path: str):
    from app.configs.storage.databases import (
        genome_connection_pool, 
        langgraph_connection_pool, 
        userdata_connection_pool
    )
    from app.core.app_container import get_container
    from langgraph.types import Command
    from app.common.constants import UserFeedbackAction
    
    
    # 1. Manually open the connection pools before initializing the container
    logger.info("🔌 Opening PostgreSQL connection pools...")
    await genome_connection_pool.open()
    await langgraph_connection_pool.open()
    await userdata_connection_pool.open()

    try:
        # 2. Initialize your agent container
        settings = get_settings()

        container = get_container()
        await container.initialize()
        agent_service = container.agent_service

        # 2. Setup the Judge and Metrics
        faithfulness_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)
        answer_rel_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)
        context_rel_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)
        context_precision_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)
        context_recall_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)

        metrics = [
            FaithfulnessMetric(
                threshold=0.5,
                model=faithfulness_judge,
                # verbose_mode=True,
                async_mode=False            # Reduce LLM call simultaneously
            ),
            AnswerRelevancyMetric(
                threshold=0.5,
                model=answer_rel_judge,
                # verbose_mode=True,
                async_mode=False
            ),
            ContextualRelevancyMetric(
                threshold=0.5,
                model=context_rel_judge,
                # verbose_mode=True,
                async_mode=False
            ),
            ContextualPrecisionMetric(
                threshold=0.5,
                model=context_precision_judge,
                # verbose_mode=True,
                async_mode=False
            ),
            ContextualRecallMetric(
                threshold=0.5,
                model=context_recall_judge,
                # verbose_mode=True,
                async_mode=False
            ),
        ]

        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"Dataset not found at: {dataset_path}")
            
        logger.info(f"Loading golden dataset from {dataset_path}...")
        with open(dataset_path, "r", encoding="utf-8") as f:
            golden_data = json.load(f)

        current_file_name = os.path.splitext(os.path.basename(__file__))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Fallback to './evaluation' if DEEPEVAL_RESULTS_FOLDER isn't in your env
        env_base_folder = os.getenv("DEEPEVAL_RESULTS_FOLDER", "./evaluation")
        
        # Convert to an absolute path so it doesn't depend on where you trigger the script
        base_eval_folder = os.path.abspath(env_base_folder)

        # Hyperparameter Sweep
        test_cases = []

        # Create the exact folder path dynamically
        folder_name = f"{current_file_name}_{timestamp}"
        run_folder = os.path.join(base_eval_folder, folder_name)
        
        # Ensure the directory actually exists before writing to it
        os.makedirs(run_folder, exist_ok=True)

        logger.info(f"Starting evaluation run. Saving results to: {run_folder}")

        for item in golden_data:
            query = item["input"]
            expected_output = item.get("expected_output", "")
            ground_truth_context = item.get("context", [])

            config = cast(RunnableConfig, {
                "configurable": {
                    "thread_id": str(uuid.uuid4())
                }
            })
            
            # 2. Run Agent
            initial_state = {
                "query": query,
                "messages": [HumanMessage(content=query)],
                "active_datasets": []
            }
            logger.info(f"Test case: '{query}' -> Starting initial graph run...")

            # The graph will run Planner and then suspend at HUMAN_REVIEW
            suspended_state = await agent_service.graph.ainvoke(initial_state, config=config)

            # 3. Simulate Human Approval
            current_thread_state = await agent_service.graph.aget_state(config)
            
            if current_thread_state.next:
                logger.info(f"Test case: '{query}' -> Graph suspended at {current_thread_state.next}. Simulating Human Approval...")
                
                # Mock the payload that the React frontend would normally send
                mock_approval = Command(
                    resume={"action": UserFeedbackAction.APPROVE}
                )
                
                # Resume the graph to trigger Executor and Synthesizer
                final_state = await agent_service.graph.ainvoke(mock_approval, config=config)
            else:
                logger.info(f"Test case: '{query}' -> Graph did not suspend. Proceeding.")
                final_state = suspended_state

            # Aggregate all sources of information used by the agent
            retrieval_context = []

            # 1. Add Vector RAG results
            retrieval_context.extend([str(res["content"]) for res in final_state.get("rag_results", [])])

            # 2. Add Tool outputs (Knowledge Graph, NCBI, etc.)
            retrieval_context.extend([str(res["output"]) for res in final_state.get("tool_results", [])])

            # 3. Add Web Search snippets
            retrieval_context.extend([str(res["content"]) for res in final_state.get("web_results", [])])

            step_answers = [
                str(msg.content) for msg in final_state.get("messages", [])
                if msg.type == "ai" and not msg.additional_kwargs.get("is_thought")
            ]
            actual_output = "\n\n".join(step_answers)

            if not actual_output.strip():
                actual_output = "The agent failed to generate an output."

            # 3. Build Test Case
            test_case = LLMTestCase(
                input=query,
                actual_output=actual_output,
                retrieval_context=retrieval_context,
                expected_output=expected_output,
                context=ground_truth_context
            )
            test_cases.append(test_case)

            dataset = EvaluationDataset()
            for tc in test_cases:
                dataset.add_test_case(tc)

            # Save dataset locally to the exact resolved path
            dataset.save_as(
                file_type="json", 
                directory=run_folder,
                include_test_cases=True
            )
            
            # 4. Execute and Persist (Use the resolved path here too!)
            evaluate(
                test_cases=dataset.test_cases,
                metrics=metrics,
                display_config=DisplayConfig(
                    results_folder=run_folder 
                ),
                async_config=AsyncConfig(max_concurrent=1)
            )
    finally:
        # 3. Always close the pools to prevent leaking connections
        logger.info("🛑 Closing PostgreSQL connection pools...")
        await genome_connection_pool.close()
        await langgraph_connection_pool.close()
        await userdata_connection_pool.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DeepEval Agentic RAG Evaluations.")
    parser.add_argument(
        "--dataset", 
        type=str, 
        required=True, 
        help="Path to the golden synthetic JSON dataset file."
    )
    
    args = parser.parse_args()

    # Pass the argument into your async loop
    asyncio.run(run_rag_evaluations(dataset_path=args.dataset))