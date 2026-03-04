import time
from loguru import logger
from typing import Dict, Any

from app.core.graph.state.agent_state import AgentState
from langchain_core.messages import SystemMessage


async def input_analyzer(state: AgentState) -> Dict[str, Any]:
    start_time = time.time()

    logger.debug("========== [Input Analyzer Node] ==========")
    logger.debug(f"State keys: {list(state.keys())}")
    logger.debug(f"Query: {state.get('query')}")

    files = state.get("uploaded_files", [])
    logger.debug(f"Uploaded files count: {len(files)}")

    file_context = ""

    if files:
        try:
            file_summary = "\n".join(
                [f"- {f.get('file_name')} (Type: {f.get('file_type')})" for f in files]
            )
            file_context = f"Attached files context:\n{file_summary}"

            logger.debug("File summary constructed")
            logger.debug(file_summary)

        except Exception as e:
            logger.exception("Failed to parse uploaded files metadata")
    else:
        logger.debug("No uploaded files provided")

    msg = SystemMessage(content=file_context) if file_context else None

    if msg:
        logger.debug("Injecting SystemMessage into state.messages")
    else:
        logger.debug("No SystemMessage injected")

    current_iter = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations")

    logger.debug(f"Iteration count: {current_iter}")
    logger.debug(f"Max iterations: {max_iter}")

    elapsed = int((time.time() - start_time) * 1000)
    logger.debug(f"Input Analyzer execution time: {elapsed} ms")

    return {
        "messages": [msg] if msg else [],
        "iteration_count": current_iter
    }