import asyncio
from enum import StrEnum
import json
import time
from typing import Literal
from langfuse import observe
from loguru import logger
from langgraph.types import Command
from langchain_core.tools import BaseTool

from app.configs.settings.settings import get_settings
from app.common.constants import ObservationType, ToolExecutionStatus
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.schemas.tool.tool_call_request import ToolCallRequest
from app.core.graph.state.agent_state import AgentState, ToolResult

def make_tools_node(available_tools: dict[str, BaseTool]):
    # @tracing(observation_type=ObservationType.TOOL)
    async def tools(state: AgentState) -> Command[
        Literal[AgentGraphNode.ENRICHMENT]
    ]:
        settings = get_settings()
        tools_to_run = state.get("required_tools", [])

        logger.debug(
            "[Tools] 🛠 Starting {count} tools for execution",
            count=len(tools_to_run)
        )

        if not tools_to_run:
            logger.debug("[Tools] No tools required.")
            return Command(
                goto=AgentGraphNode.ENRICHMENT,
                update={"tool_results": []}
            )

        overall_start = time.time()

        max_output_length = getattr(settings, 'max_tool_output_length', 20000)

        async def _execute_single_tool(tool_call) -> ToolResult:
            """Helper function to execute a single tool concurrently."""
            tool_start = time.time()
            
            # 1. Parse the tool call
            if isinstance(tool_call, ToolCallRequest):
                tool_name = str(tool_call.name)
                tool_args = getattr(tool_call, "args", {})
            elif isinstance(tool_call, dict):
                tool_name = str(tool_call.get("name", "unknown_tool"))
                tool_args = tool_call.get("args", {})
            else:
                tool_name = str(tool_call)
                tool_args = {}
            
            if not isinstance(tool_args, dict):
                tool_args = {}

            logger.debug("[Tools] Executing tool: {tool_name}", tool_name=tool_name)

            # 2. Check if tool exists
            if tool_name not in available_tools:
                error_msg = f"Tool '{tool_name}' is not recognized."
                logger.error(error_msg)
                return ToolResult(
                    tool_name=tool_name,
                    args=tool_args,
                    status=ToolExecutionStatus.ERROR,
                    output=error_msg,
                    execution_time_ms=int((time.time() - tool_start) * 1000)
                )

            # 3. Execute Tool
            try:
                tool_instance = available_tools[tool_name]
                raw_output = await tool_instance.ainvoke(tool_args)

                # Format safely
                output_text = json.dumps(raw_output) if isinstance(raw_output, (dict, list)) else str(raw_output)
                status = ToolExecutionStatus.SUCCESS

                # TRUNCATION: Protect the LLM Context Window
                if len(output_text) > max_output_length:
                    logger.warning(f"[Tools] Truncating output for {tool_name} from {len(output_text)} to {max_output_length} chars.")
                    output_text = output_text[:max_output_length] + f"\n\n[TRUNCATED: Result exceeded {max_output_length} characters]"

                elapsed = int((time.time() - tool_start) * 1000)
                logger.debug(
                    "[Tools] ✅ Tool completed | name={tool_name} | status={status} | latency={elapsed}ms",
                    tool_name=tool_name, status=status, elapsed=elapsed
                )

            except Exception as e:
                elapsed = int((time.time() - tool_start) * 1000)
                output_text = f"Tool execution failed: {str(e)}"
                status = ToolExecutionStatus.ERROR

                logger.error(
                    "[Tools] ❌ Tool failed | name={tool_name} | error={error} | latency={elapsed}ms",
                    tool_name=tool_name, error=str(e), elapsed=elapsed
                )

            return ToolResult(
                tool_name=tool_name,
                args=tool_args,
                status=status, 
                output=output_text,
                execution_time_ms=elapsed
            )
        
        # Run all tools in parallel
        tasks = [_execute_single_tool(tool_call) for tool_call in tools_to_run]
        new_tool_results = await asyncio.gather(*tasks)
        
        total_elapsed = int((time.time() - overall_start) * 1000)

        logger.debug(
            "[Tools] 🏁 All tools completed | total_tools={total_tools} | total_latency={total_latency}ms",
            total_tools=len(new_tool_results), total_latency=total_elapsed
        )

        # Return Command to route exactly to the enrichment_node
        return Command(
            goto=AgentGraphNode.ENRICHMENT,
            update={"tool_results": new_tool_results}
        )
    
    return tools