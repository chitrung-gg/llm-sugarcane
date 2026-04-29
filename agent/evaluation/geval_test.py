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
from deepeval.test_case import LLMTestCase, ToolCall, LLMTestCaseParams
from deepeval.metrics import BaseMetric, GEval
from deepeval.evaluate import AsyncConfig, DisplayConfig
from deepeval.dataset import EvaluationDataset
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from evaluation.llm_judge import GoogleGeminiJudge

def extract_tool_names_from_state(messages: List[Any]) -> List[str]:
    """
    Parses LangChain AIMessages to extract just the names of the tools executed.
    """
    executed_tools = []
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                executed_tools.append(tc.get("name", "unknown_tool"))
    return executed_tools

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
        # Note: You can route these to different models if you want to save costs on simpler metrics
        task_judge = GoogleGeminiJudge(model_name=settings.gemini_primary_model)
        efficiency_judge = GoogleGeminiJudge(model_name=settings.gemini_tertiary_model)

        # --- 1. Sugarcane RAG Quality GEval ---
        sugarcane_rag_quality_geval = GEval(
            name="Sugarcane RAG Quality",
            evaluation_steps=[
                "1. Answer Relevancy: Check if the 'actual output' directly addresses the user's specific sugarcane query (e.g., genome stats, disease traits) without drifting into unrelated topics.",
                "2. Answer Faithfulness: Verify that EVERY sugarcane fact, accession number, or gene function mentioned in the 'actual output' is strictly supported by the 'retrieval context'. Heavily penalize hallucinated facts.",
                "3. Contextual Precision & Relevancy: Assess if the 'retrieval context' contains the correct biological information. Did the retrieval pull data about the correct sugarcane variety or gene?",
                "4. Contextual Recall: Compare the 'retrieval context' against the 'expected output'. Did the system successfully retrieve all the necessary facts to formulate a complete answer?",
                "Assign a low score if the agent hallucinated data not in the context, or if the context retrieved was irrelevant to the input query."
            ],
            evaluation_params=[
                LLMTestCaseParams.INPUT, 
                LLMTestCaseParams.ACTUAL_OUTPUT, 
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.RETRIEVAL_CONTEXT
            ],
            model=task_judge,
            threshold=0.7,
            async_mode=False
        )

        # --- 2. Step Efficiency GEval ---
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
            threshold=0.7,
            async_mode=False
        )

        # --- 3. Answer Correctness GEval ---
        answer_correctness_geval = GEval(
            name="Answer Correctness",
            evaluation_steps=[
                "Compare the factual information in the 'actual output' against the 'expected output'.",
                "Check whether any facts in the 'actual output' contradict the 'expected output'.",
                "Penalize heavily for the omission of critical biological, genetic, or numerical details present in the 'expected output'.",
                "Ignore stylistic differences or phrasing variations as long as the core facts are identical."
            ],
            evaluation_params=[
                LLMTestCaseParams.INPUT, 
                LLMTestCaseParams.ACTUAL_OUTPUT, 
                LLMTestCaseParams.EXPECTED_OUTPUT
            ],
            model=task_judge,
            threshold=0.7,
            async_mode=False
        )

        # --- 4. Coherence GEval ---
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
            threshold=0.7,
            async_mode=False
        )

        # --- 5. Tonality GEval ---
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
            threshold=0.7,
            async_mode=False
        )

        # --- Define Agentic Metrics ---
        metrics: List[BaseMetric] = [
            sugarcane_rag_quality_geval,
            step_efficiency_geval,
            answer_correctness_geval,
            coherence_geval,
            tonality_geval
        ]

        # --- Define Context-Based Test Queries ---
        test_data = [
            # Test Case 1: Testing Faithfulness and Recall (NCBI Context)
            {
                "input": "Summarize the genome assembly GCA_038087645.1 based on the retrieved data.",
                "expected_output": "The genome assembly GCA_038087645.1 has a total sequence length of approximately 5.03 Gb and a GC percentage of roughly 44.5%.",
                "retrieval_context": [
                    "{'accession': 'GCA_038087645.1', 'organism': 'Saccharum officinarum x spontaneum', 'length_bp': 5038506984, 'gc_percent': 44.5}"
                ]
            },

            # Test Case 2: Testing Answer Relevancy and Precision (Neo4j Context)
            {
                "input": "What disease does the Bru1 gene provide resistance against?",
                "expected_output": "The Bru1 gene provides resistance against brown rust disease (bệnh gỉ sắt).",
                "retrieval_context": [
                    "Node: Bru1, Type: Gene, Link: [RESISTS] -> Node: Brown Rust, Type: Disease, Alias: bệnh gỉ sắt"
                ]
            },

            # Test Case 3: Testing Hallucination/Faithfulness (Vector DB Context)
            # The context explicitly mentions ROC10, but DOES NOT mention its yield. 
            # The metric will penalize the agent if it hallucinates a yield number.
            {
                "input": "What are the characteristics of the ROC10 sugarcane variety according to the database?",
                "expected_output": "ROC10 is a sugarcane variety known for its high sucrose content and good disease resistance.",
                "retrieval_context": [
                    "SCOD Document: ROC10 is a widely planted sugarcane variety originally bred in Taiwan. It is highly valued for its high sucrose content (chữ đường cao) and good disease resistance."
                ]
            }
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
            expected_output = item["expected_output"]
            
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
            
            # 1. Get Tool Names for Efficiency Metric
            actual_tool_names = extract_tool_names_from_state(final_state.get("messages", []))
            combined_actual_output = (
                f"Tools Executed: {actual_tool_names}\n\n"
                f"Final Answer: {final_state.get('final_answer', '')}"
            )

            # 2. AGGREGATE ALL CONTEXT FOR RAG METRICS (The Fix)
            actual_retrieval_context = []
            
            # Add Vector DB results (if any)
            actual_retrieval_context.extend(
                [str(res.get("content", res)) for res in final_state.get("rag_results", [])]
            )
            # Add Tool Execution results like NCBI, SCOD, Neo4j (if any)
            actual_retrieval_context.extend(
                [str(res.get("output", res)) for res in final_state.get("tool_results", [])]
            )
            # Add Web Search results (if any)
            actual_retrieval_context.extend(
                [str(res.get("snippet", res)) for res in final_state.get("web_results", [])]
            )

            # 3. Build TestCase
            test_case = LLMTestCase(
                input=query,
                actual_output=combined_actual_output, 
                expected_output=expected_output,
                retrieval_context=actual_retrieval_context # <-- Pass the aggregated context to the Judge
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