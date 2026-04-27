import time
from typing import List, Literal, Union, cast
from langfuse import observe
from loguru import logger


from app.common.constants import ObservationType
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.routing.route_action import RouteDecision, get_routing_destinations
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.core.prompts.router_prompts import ROUTER_FINAL_STATE_ENFORCEMENT, ROUTER_SYSTEM_INSTRUCTIONS

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import render_text_description_and_args, BaseTool
from langgraph.types import Command

def make_router_node(
    llm_service: LLMService,
    available_tools: dict[str, BaseTool]
):
    @tracing(observation_type=ObservationType.CHAIN)
    async def router(state: AgentState) -> Command[
        Literal[
            AgentGraphNode.RAG,
            AgentGraphNode.TOOL,
            AgentGraphNode.WEB_SEARCH,
            AgentGraphNode.SYNTHESIZER,
        ]
    ]:
        settings = get_settings()
        
        logger.debug("[Router] 🧭 Starting intent analysis")

        current_iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)

        if current_iteration >= max_iterations:
            logger.warning(f"[Router] 🛑 Max iterations reached ({current_iteration}). Forcing exit to synthesizer.")
            return Command(
                goto=AgentGraphNode.SYNTHESIZER,
                update={"iteration_count": current_iteration + 1}
            )

        start_time = time.time()

        query = state["query"]
        logger.debug(f"[Router] Query: {query}")

        router_llm = llm_service.get_structured_primary_model(RouteDecision)

        tool_list_str = render_text_description_and_args(list(available_tools.values()))

        rag_results = state.get("rag_results", [])
        tool_results = state.get("tool_results", [])
        web_results = state.get("web_results", [])

        max_rag_results_length = getattr(settings, 'max_rag_results_length', 1000)
        max_web_results_length = getattr(settings, 'max_web_results_length', 1000)
        max_tool_results_length = getattr(settings, 'max_tool_results_length', 3000)


        execution_history = ""
        failed_tools = []
        
        if rag_results or tool_results or web_results:
            execution_history += "\n--- CURRENT SEARCH/TOOL RESULTS ---\n"
            
            if rag_results:
                rag_preview = str(rag_results)[:max_rag_results_length] + "..." if len(str(rag_results)) > max_rag_results_length else str(rag_results)
                execution_history += (
                    f"⛔ ALREADY EXECUTED: Local RAG for query: '{query}'\n"
                    f"  Preview: {rag_preview}\n"
                    f"  -> RULE: DO NOT use 'rag_only' again.\n\n"
                )
            
            if web_results:
                web_preview = str(web_results)[:max_web_results_length] + "..." if len(str(web_results)) > max_web_results_length else str(web_results)
                execution_history += (
                    f"⛔ ALREADY EXECUTED: Web Search for query: '{query}'\n"
                    f"  Result Preview ({len(web_results)} items): {web_preview}\n"
                    f"  -> RULE: The previous 'web_search' for this query did not yield a complete answer. If you choose to search again, you MUST use significantly different keywords or a more specific search query.\n\n"
                )

            if tool_results:
                execution_history += "- Tool History:\n"
                for res in tool_results:
                    status_emoji = "✅" if res['status'] == "success" else "❌"

                    if res['status'] == "error":
                        failed_tools.append(res['tool_name'])

                    tool_args = res.get('args', {})
                    execution_history += f"  {status_emoji} {res['tool_name']}({tool_args}): {res['output'][:max_tool_results_length]}...\n"

        failover_instruction = ""
        if failed_tools:
            failed_str = ", ".join(set(failed_tools))
            failover_instruction = (
                f"\nFAIL-OVER ALERT: The tools [{failed_str}] failed in the last step. "
                f"Read the error messages in the Tool History carefully. You may retry a failed tool "
                f"ONLY IF you provide corrected arguments. DO NOT repeat the exact same failed call!\n"
            )

        # --- DYNAMIC INTENTS BUILDER ---
        available_intents_list = [
            "- 'direct_answer': Use ONLY when the answer is complete OR no further improvement is possible.",
            "- 'all': Use this to run local document RAG *AND* Bioinformatics/Knowledge Graph tools simultaneously. Best for comprehensive research.",
            "- 'tool_only': For specialized bioinformatics analysis OR searching the Knowledge Graph."
        ]
        
        if not web_results:
            available_intents_list.append("- 'web_search': For latest or external information.")
            
        if not rag_results:
            available_intents_list.append("- 'rag_only': For simple local document keyword lookups.")
        
        intents_str = "\n            ".join(available_intents_list)

        # 1. Build the Dynamic Workspace Context
        active_project = state.get("active_project_name", "Default Project")
        active_datasets = state.get("active_datasets", [])
        
        if not active_datasets:
            workspace_str = f"ACTIVE PROJECT: {active_project}\nNo active genomic datasets selected."
        else:
            blocks = [f"=== ACTIVE WORKSPACE: {active_project} ==="]
            for idx, ds in enumerate(active_datasets, 1):
                source_type = "User Uploaded" if ds.get("is_user_uploaded") else "System Native"
                block = (
                    f"Dataset {idx}: {ds.get('dataset_name')} ({source_type})\n"
                    f" - dataset_id: {ds.get('dataset_id')}\n"
                    f" - fasta_uri: {ds.get('fasta_uri', 'N/A')}\n"
                    f" - gff3_uri: {ds.get('gff3_uri', 'N/A')}"
                )
                blocks.append(block)
            
            blocks.append(
                "CRITICAL: When running backend tools, you MUST use the exact `dataset_id` listed above."
            )
            workspace_str = "\n\n".join(blocks)

        # 2. Format the Base System Instructions
        system_instructions = ROUTER_SYSTEM_INSTRUCTIONS.format(
            workspace_context=workspace_str,
            file_context=state.get('file_context', 'No files uploaded.'),
            tool_list_str=tool_list_str,
            conversation_summary=state.get('summary', 'No summary available yet.')
        )

        messages_to_send: List[BaseMessage] = [
            SystemMessage(content=system_instructions)
        ]

        # 2. Add conversation history
        if state.get("messages"):
            messages_to_send.extend(state["messages"])
        else:
            messages_to_send.append(HumanMessage(content=f"User Query: {query}"))

        # 3. Inject the State, Previews and Anti-Loop Rules.
        final_state_enforcement = ROUTER_FINAL_STATE_ENFORCEMENT.format(
            execution_history=execution_history,
            failover_instruction=failover_instruction,
            intents_str=intents_str
        )

        # Append as a SystemMessage at the end of the array to force compliance
        messages_to_send.append(SystemMessage(content=final_state_enforcement))
        
        logger.debug(
            f"[Router] Sending {len(messages_to_send)} messages to LLM (Iteration: {current_iteration})"
        )

        try:
            decision: RouteDecision = await router_llm.ainvoke(messages_to_send)

        except Exception as e:
            logger.exception("[Router] ❌ LLM routing failed")
            raise e
        
        destinations = cast(
            Union[
                Literal[
                    AgentGraphNode.RAG,
                    AgentGraphNode.TOOL,
                    AgentGraphNode.WEB_SEARCH,
                    AgentGraphNode.SYNTHESIZER,
                ],
                List[
                    Literal[
                        AgentGraphNode.RAG,
                        AgentGraphNode.TOOL,
                        AgentGraphNode.WEB_SEARCH,
                        AgentGraphNode.SYNTHESIZER,
                    ]
                ]
            ],
            get_routing_destinations(decision.intent)
        )

        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[Router] ✅ Decision: {decision.intent} | Tools: {decision.required_tools} | Reasoning: {decision.reasoning[:1000]} | Latency: {elapsed}ms"
        )

        return Command(
            goto=destinations,
            update={
                "required_tools": decision.required_tools,
                "iteration_count": current_iteration + 1,
                "last_intent": decision.intent,
                "router_guidance": decision.reasoning
            }
        )

    return router