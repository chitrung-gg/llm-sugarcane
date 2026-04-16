from enum import StrEnum
import time
from typing import List, Literal, Union, cast
from loguru import logger


from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.routing.route_action import RouteDecision, get_routing_destinations
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import render_text_description_and_args, BaseTool
from langgraph.types import Command

def make_router_node(
    llm_service: LLMService,
    available_tools: dict[str, BaseTool]
):
    async def router(state: AgentState) -> Command[
        Literal[
            AgentGraphNode.RAG,
            AgentGraphNode.TOOL,
            AgentGraphNode.WEB_SEARCH,
            AgentGraphNode.SYNTHESIZER,
        ]
    ]:
        logger.debug("[Router] 🧭 Starting intent analysis")

        current_iteration = state.get("iteration_count", 0)

        if current_iteration >= 3:
            logger.warning(f"[Router] 🛑 Max iterations reached ({current_iteration}). Forcing exit to synthesizer.")
            return Command(
                goto=AgentGraphNode.SYNTHESIZER,
                update={"iteration_count": current_iteration + 1}
            )

        start_time = time.time()

        query = state["query"]
        logger.debug(f"[Router] Query: {query}")

        llm = llm_service.get_primary_model()
        router_llm = llm.with_structured_output(RouteDecision)

        tool_list_str = render_text_description_and_args(list(available_tools.values()))

        rag_results = state.get("rag_results", [])
        tool_results = state.get("tool_results", [])
        web_results = state.get("web_results", [])

        execution_history = ""
        failed_tools = []
        
        if rag_results or tool_results or web_results:
            execution_history += "\n--- CURRENT SEARCH/TOOL RESULTS ---\n"
            
            if rag_results:
                rag_preview = str(rag_results)[:500] + "..." if len(str(rag_results)) > 500 else str(rag_results)
                execution_history += (
                    f"⛔ ALREADY EXECUTED: Local RAG for query: '{query}'\n"
                    f"  Preview: {rag_preview}\n"
                    f"  -> RULE: DO NOT use 'rag_only' again.\n\n"
                )
            
            if web_results:
                web_preview = str(web_results)[:600] + "..." if len(str(web_results)) > 600 else str(web_results)
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
                    execution_history += f"  {status_emoji} {res['tool_name']}({tool_args}): {res['output'][:3000]}...\n"

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

        # 1. Base System Instructions (Static knowledge)
        system_instructions = f"""
            You are an expert routing assistant for a Sugarcane Genomics system.
            Your job is to analyze the user's query and route it to the correct execution path.

            AVAILABLE BIOINFORMATICS TOOLS:
            {tool_list_str}

            CONVERSATION SUMMARY
            {state.get('summary', 'No summary available yet.')}
        """

        messages_to_send: List[BaseMessage] = [
            SystemMessage(content=system_instructions)
        ]

        # 2. Add conversation history
        if state.get("messages"):
            messages_to_send.extend(state["messages"])
        else:
            messages_to_send.append(HumanMessage(content=f"User Query: {query}"))

        # 3. Inject the State, Previews and Anti-Loop Rules at the VERY END.
        final_state_enforcement = f"""
            {execution_history}
            {failover_instruction}

            CRITICAL ROUTING RULES & ANTI-LOOP MECHANISM:

            1. EVALUATE TOOL RESULTS & RECOVERY:
            - If information is FULLY sufficient → choose 'direct_answer'
            - If a tool fails (e.g., missing a required ID or field), read the error output. You are ENCOURAGED to call the tool again WITH the corrected or missing arguments.

            2. LAZY BACKEND EXECUTION:
            - Only invoke heavy computational backend tools (e.g., run_blast, synteny) if the user explicitly asks for them.
            - Do not blindly guess IDs for backend tools. If a tool requires a `genome_id` or `file_id` that you don't know, use `search_knowledge_graph` or other lookup tools FIRST to find the correct ID before running the heavy computation.

            3. STRICT ANTI-LOOP RULE:
            - If you see "ALREADY EXECUTED" in the history for RAG or Web Search, do not run them again.
            - If you repeat a failed tool call without changing the arguments to fix the error, the system will crash. Move to 'direct_answer' if you cannot figure out the correct arguments.

            4. MANDATORY TOOL CALLING RULES (CRITICAL):
            - If you choose 'tool_only' or 'all', you MUST extract the necessary tools and populate the `required_tools` list with the correct tool name and arguments. 
            - DO NOT output an empty tool list if you intend to use bioinformatics tools.
            - TRANSLATION & KEYWORD EXTRACTION: If the user's query is in Vietnamese (e.g., "mía r570"), you MUST translate and extract short English keywords (e.g., "sugarcane r570") before passing it into the tool arguments.

            ---

            AVAILABLE INTENTS FOR THIS ITERATION:
            {intents_str}
            (Note: If you select 'all' or 'tool_only', you MUST provide the tool details in `required_tools`)
        """

        # Append as a SystemMessage at the end of the array to force compliance
        messages_to_send.append(SystemMessage(content=final_state_enforcement))
        
        logger.debug(
            f"[Router] Sending {len(messages_to_send)} messages to LLM (Iteration: {current_iteration})"
        )

        try:
            raw_decision = await router_llm.ainvoke(messages_to_send)
            decision = RouteDecision.model_validate(raw_decision)

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