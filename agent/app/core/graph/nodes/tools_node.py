import json
import time
from typing import Literal
from loguru import logger
from langgraph.types import Command
from langchain_core.tools import BaseTool

from agent.app.core.app_container import get_container
from app.schemas.tool.tool_call_request import ToolCallRequest
from app.core.tools.genome_tool import (
    design_polyploid_primer, get_gene_detail,
    get_genes_list, list_genome_files, run_blast, run_crispor,
    run_synteny_analysis, search_genes_full
)
from app.core.graph.state.agent_state import AgentState, ToolResult


after_tools_node = Literal["synthesizer"]

def get_all_available_tools() -> dict[str, BaseTool]:
    """
    Dynamically build the tool dictionary including OpenAPI tools.

    Because each method return the name depends on the OpenAPI specs, and can be changed over time, so we should build the list dynamically
    """
    static_tools = [
        list_genome_files,
        get_genes_list, search_genes_full,
        get_gene_detail, run_blast,
        run_synteny_analysis, run_crispor, design_polyploid_primer
    ]

    tool_dict = {
        tool.name: tool for tool in static_tools
    }

    # Merge in the dynamic NCBI tools from the container
    container = get_container()
    for ncbi_tool in container.ncbi_tools:
        tool_dict[ncbi_tool.name] = ncbi_tool
        
    return tool_dict
    
async def tools(state: AgentState) -> Command[after_tools_node]:
    tools_to_run = state.get("required_tools", [])

    # Get all tools (Static + OpenAPI)
    available_tools = get_all_available_tools()

    logger.debug(
        "[Tools] 🛠 Starting {count} tools for execution",
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

    for tool_call in tools_to_run:
        # Parse the tool call
        if isinstance(tool_call, ToolCallRequest):
            # It's a Pydantic object (ToolCallRequest)
            tool_name = str(tool_call.name)
            tool_args = getattr(tool_call, "args", {})
        elif isinstance(tool_call, dict):
            # It's a dictionary
            tool_name = str(tool_call.get("name", "unknown_tool"))
            tool_args = tool_call.get("args", {})
        else:
            # Fallback if it's just a raw string
            tool_name = str(tool_call)
            tool_args = {}
        
        if not isinstance(tool_args, dict):
            tool_args = {}

        logger.debug("[Tools] Executing tool: {tool_name}", tool_name=tool_name)
        tool_start = time.time()

        if tool_name not in available_tools:
            error_msg = f"Tool '{tool_name}' is not recognized."
            logger.error(error_msg)
            new_tool_results.append(ToolResult(
                tool_name=tool_name, status="error", output=error_msg, execution_time_ms=0
            ))
            continue

        try:
            # Execute the actual LangChain tool
            tool_instance = available_tools[tool_name]
            raw_output = await tool_instance.ainvoke(tool_args)     # async
            
            # Format output safely to string
            output_text = json.dumps(raw_output) if isinstance(raw_output, (dict, list)) else str(raw_output)
            status = "success"

            elapsed = int((time.time() - tool_start) * 1000)
            logger.debug(
                "[Tools] ✅ Tool completed | name={tool_name} | status={status} | latency={elapsed}ms",
                tool_name=tool_name, status=status, elapsed=elapsed
            )

        except Exception as e:
            elapsed = int((time.time() - tool_start) * 1000)
            output_text = f"Tool execution failed: {str(e)}"
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