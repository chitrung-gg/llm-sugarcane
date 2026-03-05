import time
from loguru import logger

from app.core.graph.state.agent_state import AgentState, ToolResult


async def tools(state: AgentState) -> dict:
    tools_to_run = state.get("required_tools", [])

    logger.debug(
        f"[Tools] 🛠 Starting tool execution | count={len(tools_to_run)}"
    )

    if not tools_to_run:
        logger.debug("[Tools] No tools required.")
        return {"tool_results": []}

    overall_start = time.time()
    new_tool_results = []

    for tool_name in tools_to_run:
        logger.debug(f"[Tools] Executing tool: {tool_name}")

        tool_start = time.time()

        try:
            # TODO: Replace with real tool logic
            output_text = f"Simulated successful execution of {tool_name}."
            status = "success"

            elapsed = int((time.time() - tool_start) * 1000)

            logger.debug(
                f"[Tools] ✅ Tool completed | "
                f"name={tool_name} | "
                f"status={status} | "
                f"latency={elapsed}ms"
            )

        except Exception as e:
            elapsed = int((time.time() - tool_start) * 1000)
            output_text = str(e)
            status = "error"

            logger.exception(
                f"[Tools] ❌ Tool failed | "
                f"name={tool_name} | "
                f"latency={elapsed}ms"
            )

        tool_item = ToolResult(
            tool_name=tool_name,
            status=status, 
            output=output_text,
            execution_time_ms=elapsed
        )
        new_tool_results.append(tool_item)

    total_elapsed = int((time.time() - overall_start) * 1000)

    logger.debug(
        f"[Tools] 🏁 All tools completed | "
        f"total_tools={len(new_tool_results)} | "
        f"total_latency={total_elapsed}ms"
    )

    return {"tool_results": new_tool_results}