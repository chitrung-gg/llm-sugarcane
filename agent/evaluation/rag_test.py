from typing import Any, cast
import os
from datetime import datetime
import uuid
from loguru import logger
import asyncio
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage

from evaluation.llm_judge import GoogleGeminiJudge
from app.configs.loggings.loggings import setup_logging
from app.configs.settings.settings import get_settings

os.environ["DEEPEVAL_TIMEOUT"] = "600"
setup_logging()

from deepeval import assert_test, evaluate
from deepeval.evaluate import AsyncConfig, DisplayConfig
from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase
from deepeval.metrics import ContextualPrecisionMetric, ContextualRecallMetric, FaithfulnessMetric, AnswerRelevancyMetric, ContextualRelevancyMetric


    
async def run_rag_evaluations():
    from app.configs.storage.databases import (
        genome_connection_pool, 
        langgraph_connection_pool, 
        userdata_connection_pool
    )
    from app.core.app_container import get_container
    
    
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
        faithfulness_judge = GoogleGeminiJudge(model_name=settings.GEMINI_PRIMARY_MODEL)
        answer_rel_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)
        context_rel_judge = GoogleGeminiJudge(model_name=settings.GEMINI_TERTIARY_MODEL)

        metrics = [
            FaithfulnessMetric(
                threshold=0.7,
                model=faithfulness_judge,
                verbose_mode=True,
                async_mode=False            # Reduce LLM call simultaneously
            ),
            AnswerRelevancyMetric(
                threshold=0.7,
                model=answer_rel_judge,
                verbose_mode=True,
                async_mode=False
            ),
            ContextualRelevancyMetric(
                threshold=0.7,
                model=context_rel_judge,
                verbose_mode=True,
                async_mode=False
            ),
        ]

        queries = [
            "What are the key genes involved in sugarcane sucrose metabolism?",
            # "How does drought stress affect sugarcane yield according to recent studies?"
        ]

        current_file_name = os.path.splitext(os.path.basename(__file__))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Fallback to './evaluation' if DEEPEVAL_RESULTS_FOLDER isn't in your env
        env_base_folder = os.getenv("DEEPEVAL_RESULTS_FOLDER", "./evaluation")
        
        # Convert to an absolute path so it doesn't depend on where you trigger the script
        base_eval_folder = os.path.abspath(env_base_folder)

        # Hyperparameter Sweep
        for temp in [0.0]:
            test_cases = []

            # Create the exact folder path dynamically
            folder_name = f"{current_file_name}_{timestamp}_temp_{temp}"
            run_folder = os.path.join(base_eval_folder, folder_name)
            
            # Ensure the directory actually exists before writing to it
            os.makedirs(run_folder, exist_ok=True)

            logger.info(f"Starting evaluation run. Saving results to: {run_folder}")

            for query in queries:
                config = cast(RunnableConfig, {
                    "configurable": {
                        "thread_id": str(uuid.uuid4())
                    }
                })
                
                # 2. Run Agent
                initial_state = {
                    "query": query,
                    "messages": [HumanMessage(content=query)],
                    "active_datasets": [],
                    "iteration_count": 0,
                }
                final_state = await agent_service.graph.ainvoke(initial_state, config=config)
                
                # Aggregate all sources of information used by the agent
                retrieval_context = []

                # 1. Add Vector RAG results
                retrieval_context.extend([str(res["content"]) for res in final_state.get("rag_results", [])])

                # 2. Add Tool outputs (Knowledge Graph, NCBI, etc.)
                retrieval_context.extend([str(res["output"]) for res in final_state.get("tool_results", [])])

                # 3. Add Web Search snippets
                retrieval_context.extend([str(res["snippet"]) for res in final_state.get("web_results", [])])

                test_case = LLMTestCase(
                    input=query,
                    actual_output=str(final_state.get("final_answer", "")),
                    retrieval_context=retrieval_context # Now includes all retrieved data
                )
                # 3. Build Test Case
                test_case = LLMTestCase(
                    input=query,
                    actual_output=str(final_state.get("final_answer", "")),
                    retrieval_context=[str(res["content"]) for res in final_state.get("rag_results", [])]
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
    asyncio.run(run_rag_evaluations())