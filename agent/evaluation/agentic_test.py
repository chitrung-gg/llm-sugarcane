import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, cast
import uuid

from app.common.constants import UserFeedbackAction
from app.configs.loggings.loggings import setup_logging
from app.configs.settings.settings import get_settings

os.environ["DEEPEVAL_TIMEOUT"] = "6000"
setup_logging()

from deepeval import evaluate
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import (
    ToolCorrectnessMetric, 
    ArgumentCorrectnessMetric
)
from deepeval.evaluate import AsyncConfig, DisplayConfig
from deepeval.dataset import EvaluationDataset
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from loguru import logger

from evaluation.llm_judge import GoogleGeminiJudge

def extract_tool_calls_from_state(state: Dict[str, Any]) -> List[ToolCall]:
    """
    Parses the LangGraph state to extract tool execution histories.
    Directly targets the 'tool_results' and 'web_results' arrays used by the architecture.
    """
    deepeval_tools: List[ToolCall] = []

    # 1. Look directly at the 'tool_results' array revealed by the debugger
    tool_results = state.get("tool_results", [])
    
    for tr in tool_results:
        if isinstance(tr, dict) and "tool_name" in tr:
            deepeval_tools.append(
                ToolCall(
                    name=tr.get("tool_name", "unknown_tool"),
                    input_parameters=tr.get("args", {})
                )
            )

    # 2. Also check 'web_results' just in case web searches are logged here
    web_results = state.get("web_results", [])
    for wr in web_results:
        if isinstance(wr, dict) and "tool_name" in wr:
            deepeval_tools.append(
                ToolCall(
                    name=wr.get("tool_name", "unknown_tool"),
                    input_parameters=wr.get("args", {})
                )
            )

    # 3. Remove exact duplicates
    unique_tools: List[ToolCall] = []
    seen = set()

    for tool in deepeval_tools:
        # Create a string representation to check for uniqueness
        tool_repr = f"{tool.name}_{json.dumps(tool.input_parameters, sort_keys=True)}"
        if tool_repr not in seen:
            seen.add(tool_repr)
            unique_tools.append(tool)

    return unique_tools

async def run_agentic_evaluations(dataset_path: str):
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
        tool_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)
        arg_judge = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)

        # --- Define Agentic Metrics ---
        metrics = [
            ToolCorrectnessMetric(
                threshold=0.7, 
                model=tool_judge, 
                async_mode=False
            ),
            ArgumentCorrectnessMetric(
                threshold=0.7, 
                model=arg_judge, 
                async_mode=False
            )
        ]

        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"Dataset not found at: {dataset_path}")
            
        logger.info(f"Loading agentic dataset from {dataset_path}...")
        with open(dataset_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            
        test_data = []
        for item in raw_data:
            expected_tools = []
            for tc in item.get("expected_tools", []):
                expected_tools.append(
                    ToolCall(
                        name=tc.get("name"),
                        input_parameters=tc.get("input_parameters", {})
                    )
                )
            test_data.append({
                "input": item["input"],
                "expected_tools": expected_tools
            })

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

            # 1. Run until it hits the Human Approval breakpoint
            suspended_state = await asyncio.wait_for(
                agent_service.graph.ainvoke(initial_state, config=config),
                timeout=1000 
            )
            
            # 2. Check if the graph suspended
            current_thread_state = await agent_service.graph.aget_state(config)
            
            if current_thread_state.next:
                logger.info(f"Test case: '{query}' -> Graph suspended. Simulating Human Approval...")
                
                # Create the mock approval command
                mock_approval = Command(
                    resume={"action": UserFeedbackAction.APPROVE}
                )
                
                # Resume the graph so it actually runs the tools!
                final_state = await agent_service.graph.ainvoke(mock_approval, config=config)
            else:
                logger.info(f"Test case: '{query}' -> Graph did not suspend. Proceeding.")
                final_state = suspended_state

            # --- Extract LangGraph Tool Calls ---
            actual_tool_calls = extract_tool_calls_from_state(final_state)
            logger.info(f"DeepEval Extracted Tools: {[tc.name for tc in actual_tool_calls]}")
            
            # --- Extract Actual Output Robustly ---
            # Even though we are testing tools, DeepEval requires *some* actual_output string to not crash.
            actual_output = final_state.get("final_answer", "")
            if not actual_output:
                messages = final_state.get("messages", [])
                for msg in reversed(messages):
                    if getattr(msg, "type", "") == "ai" and msg.content:
                        actual_output = str(msg.content)
                        break
                        
            if not actual_output or not actual_output.strip():
                actual_output = "The agent did not generate a text response."
            
            # --- Build TestCase ---
            test_case = LLMTestCase(
                input=query,
                actual_output=actual_output,
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
    parser = argparse.ArgumentParser(description="Run DeepEval Tool Evaluations.")
    parser.add_argument(
        "--dataset", 
        type=str, 
        required=True, 
        help="Path to the agentic JSON dataset file."
    )
    args = parser.parse_args()
    asyncio.run(run_agentic_evaluations(dataset_path=args.dataset))