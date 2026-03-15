import time
from typing import Literal
from loguru import logger
from langgraph.types import Command

from app.core.graph.state.agent_state import AgentState, ToolResult


after_tools_node = Literal["synthesizer"]

async def tools(state: AgentState) -> Command[after_tools_node]:
    tools_to_run = state.get("required_tools", [])

    logger.debug(
        "[Tools] 🛠 Starting tool execution | count={count}",
        count=len(tools_to_run)
    )

    if not tools_to_run:
        logger.debug("[Tools] No tools required.")
        return Command(
            goto="synthesizer",
            update={"tool_results": []}
        )

    overall_start = time.time()
    new_tool_results = []

    for tool_name in tools_to_run:
        logger.debug("[Tools] Executing tool: {tool_name}", tool_name=tool_name)

        tool_start = time.time()

        try:
            # TODO: Replace with real tool logic
            output_text = f"Simulated successful execution of {tool_name}."
            status = "success"

            elapsed = int((time.time() - tool_start) * 1000)

            logger.debug(
                "[Tools] ✅ Tool completed | name={tool_name} | status={status} | latency={elapsed}ms",
                tool_name=tool_name, status=status, elapsed=elapsed
            )

        except Exception as e:
            elapsed = int((time.time() - tool_start) * 1000)
            output_text = str(e)
            status = "error"

            logger.exception(
                "[Tools] ❌ Tool failed | name={tool_name} | latency={elapsed}ms",
                tool_name=tool_name, elapsed=elapsed
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
        "[Tools] 🏁 All tools completed | total_tools={total_tools} | total_latency={total_latency}ms",
        total_tools=len(new_tool_results), total_latency=total_elapsed
    )

    # Return Command to route exactly to the synthesizer
    return Command(
        goto="synthesizer",
        update={"tool_results": new_tool_results}
    )