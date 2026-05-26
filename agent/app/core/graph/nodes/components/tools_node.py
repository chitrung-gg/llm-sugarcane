import asyncio
from enum import StrEnum
import json
import time
from typing import Dict, Literal
from langfuse import observe
from loguru import logger
from langchain_core.tools import BaseTool

from app.configs.settings.settings import get_settings
from app.common.constants import ObservationType, ToolExecutionStatus
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.schemas.tool.tool_call_request import ToolCallRequest
from app.core.graph.state.agent_state import AgentState, ToolResult
from app.core.tools.registry.ingestion_config_tool import IngestionConfig

def make_tools_node(available_tools: dict[str, BaseTool], tool_registry: Dict[str, IngestionConfig]):
    @tracing(observation_type=ObservationType.TOOL)
    async def tools(state: AgentState) -> dict:
        settings = get_settings()
        tools_to_run = state.get("required_tools", [])

        logger.debug(
            "[Tools] Starting {count} tools for execution",
            count=len(tools_to_run)
        )

        if not tools_to_run:
            logger.debug("[Tools] No tools required.")
            return {
                "tool_results": [],
                "extracted_knowledge": []
            }

        overall_start = time.time()

        max_output_length = settings.TOOLS_MAX_TOOL_OUTPUT_LENGTH

        async def _execute_single_tool(tool_call) -> ToolResult:
            """Helper function to execute a single tool concurrently."""
            tool_start = time.time()
            
            tool_name = str(tool_call.name)
            tool_args = tool_call.args

            logger.debug("[Tools] Executing tool: {tool_name}", tool_name=tool_name)

            # 1. Check if tool exists
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

            # 2. Execute Tool
            try:
                tool_instance = available_tools[tool_name]
                raw_output = await tool_instance.ainvoke(tool_args)

                # Format safely
                try:
                    if isinstance(raw_output, (dict, list)):
                        # default=str handles datetimes, UUIDs, and custom objects gracefully
                        output_text = json.dumps(raw_output, default=str) 
                    else:
                        output_text = str(raw_output)
                except Exception as parse_err:
                    logger.warning(f"[Tools] JSON serialization failed for {tool_name}, falling back to str(): {parse_err}")
                    output_text = str(raw_output)

                status = ToolExecutionStatus.SUCCESS

                # Protect the LLM Context Window
                if len(output_text) > max_output_length:
                    logger.warning(f"[Tools] Truncating output for {tool_name} from {len(output_text)} to {max_output_length} chars.")
                    output_text = output_text[:max_output_length] + f"\n\n[TRUNCATED: Result exceeded {max_output_length} characters]"

                elapsed = int((time.time() - tool_start) * 1000)
                logger.debug(
                    "[Tools] Tool completed | name={tool_name} | status={status} | latency={elapsed}ms",
                    tool_name=tool_name, status=status, elapsed=elapsed
                )

            except Exception as e:
                elapsed = int((time.time() - tool_start) * 1000)
                output_text = f"Tool execution failed: {type(e).__name__} - {str(e)}"
                status = ToolExecutionStatus.ERROR

                logger.error(
                    "[Tools] Tool failed | name={tool_name} | error={error} | latency={elapsed}ms",
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
            "[Tools] All tools completed | total_tools={total_tools} | total_latency={total_latency}ms",
            total_tools=len(new_tool_results), total_latency=total_elapsed
        )

        # Used for knowledge graph ingestion dynamically if using NCBI Tools
        # extracted_knowledge = []
        # active_project = state.get("active_project") or {}
        # project_id = active_project.get("project_id", "unknown")

        # for result in new_tool_results:
        #     if result["status"] == ToolExecutionStatus.SUCCESS and result["tool_name"] in tool_registry:
        #         logger.info(f"[Tools] Queueing knowledge graph ingestion for: {result['tool_name']}")
                # extracted_knowledge.append({
                #     "source_text": result["output"],
                #     "source_metadata": {
                #         "tool": result["tool_name"],
                #         "project_id": project_id
                #     }
                # })

        return {
            "tool_results": new_tool_results,
            # "extracted_knowledge": extracted_knowledge
        }


    return tools