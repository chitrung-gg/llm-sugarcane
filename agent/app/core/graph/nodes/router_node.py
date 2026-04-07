import time
from typing import Literal, Union
from loguru import logger

from app.core.graph.routing.route_action import RouteDecision, get_routing_destinations
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import render_text_description_and_args, BaseTool
from langgraph.types import Command

after_router_node = Literal["rag_execution", "tool_execution", "web_search", "synthesizer"]

def make_router_node(
    llm_service: LLMService,
    available_tools: dict[str, BaseTool]
):
    async def router(state: AgentState) -> Command[after_router_node]:
        logger.debug("[Router] 🧭 Starting intent analysis")

        current_iteration = state.get("iteration_count", 0)

        if current_iteration >= 3:
            logger.warning(f"[Router] 🛑 Max iterations reached ({current_iteration}). Forcing exit to synthesizer.")
            return Command(
                goto="synthesizer",
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
                execution_history += f"- Found {len(rag_results)} chunks from local RAG.\n"
            if tool_results:
                execution_history += "- Tool History:\n"
                for res in tool_results:
                    status_emoji = "✅" if res['status'] == "success" else "❌"

                    if res['status'] == "error":
                        failed_tools.append(res['tool_name'])

                    tool_args = res.get('args', {})
                    execution_history += f"  {status_emoji} {res['tool_name']}({tool_args}): {res['output'][:300]}...\n"
            if web_results:
                execution_history += f"- Found {len(web_results)} web results.\n"
            
            execution_history += """
                REASONING GUIDELINES:
                1. If the results above are SUFFICIENT to fully answer the user, choose 'direct_answer' to finish.
                2. If a tool returned 'Unknown', 'Error', or generic metadata (like 'GCA_...' without names), DO NOT repeat it. Instead, try a different tool.
                3. If you have partial info, decide which specific tool can fill the remaining gap.
                4. AVOID REDUNDANT CALLS: DO NOT call the exact same tool with the exact same arguments if it already succeeded in the current EXECUTION HISTORY. If you are still missing information but have no other appropriate tools to fetch it, you MUST choose 'direct_answer' to proceed to the synthesizer.
            """

        failover_instruction = ""
        if failed_tools:
            failed_str = ", ".join(set(failed_tools))
            failover_instruction = f"\nFAIL-OVER ALERT: The following tools FAILED or TIMED OUT in the previous step: [{failed_str}]. DO NOT USE THEM AGAIN! Route to 'web_search', 'rag_only', or use alternative available tools.\n"

        
        system_instructions = f"""
            You are an expert routing assistant for a Sugarcane Genomics system.
            Your job is to analyze the user's query and route it to the correct execution path.

            AVAILABLE BIOINFORMATICS TOOLS:
            {tool_list_str}

            CONVERSATION SUMMARY
            {state.get('summary', 'No summary available yet.')}

            EXECUTION HISTORY
            {execution_history if execution_history else "No tools have been run yet."}

            FAILOVER INSTRUCTION
            {failover_instruction}

            CRITICAL ROUTING RULES:
            - Choose 'direct_answer': If you have enough information to answer, or if the user asks a simple question (about uploaded files or not).
            - Choose 'all' (RECOMMENDED FOR FIRST TURN): For general biological queries.
            - Choose 'web_search': For latest news or when internal databases (RAG/Tools) fail.
            - Choose 'rag_only': For queries specifically about local documents.
            - Choose 'tool_only': For specialized bioinformatic analyses (NCBI, BLAST, etc.).
               * EXCEPTION: DO NOT use local backend tools (like list_genome_files, get_genes_list) for general information queries. ONLY use them if the user EXPLICITLY specifies running a tool or querying their uploaded backend files.

            CRITICAL: Use EXACT tool names. Do not hallucinate tools.
        """
        
        user_input = f"User Query: {query}"

        messages_to_send = [
            SystemMessage(content=system_instructions),
            HumanMessage(content=user_input),
        ]

        # Include previous chat history if it exists
        if state.get("messages"):
            # history_messages = state["messages"]
            # logger.debug(
            #     f"[Router] Including chat history | total_messages={len(history_messages)}"
            # )
            
            # # 1. Extract up to the last 5 messages
            # last_5_msgs = history_messages[-5:]
            
            # logger.debug("[Router] --- Last 5 Messages in Context ---")
            # for idx, msg in enumerate(last_5_msgs):
            #     # Identify if it is a HumanMessage, AIMessage, etc.
            #     msg_type = msg.__class__.__name__ 
                
            #     # Truncate the content to 150 characters for clean terminal output
            #     raw_content = str(msg.content).replace("\n", " ")
            #     content_preview = raw_content[:150] + ("..." if len(raw_content) > 150 else "")
                
            #     logger.debug(f"  {idx + 1}. [{msg_type}]: {content_preview}")
            # logger.debug("--------------------------------------------")

            # # 2. Append the history to the prompt
            # # Pro-tip: If conversations get very long, you might want to change this to:
            # # messages_to_send.extend(history_messages[-10:]) 
            # # to prevent the Router from exceeding its context window!

            # Already use the @summarizer_node to summarize the content 
            messages_to_send.extend(state["messages"])
        
        logger.debug(
            f"[Router] Sending {len(messages_to_send)} messages to LLM (Iteration: {current_iteration})"
        )

        try:
            raw_decision = await router_llm.ainvoke(messages_to_send)
            decision = RouteDecision.model_validate(raw_decision)

        except Exception as e:
            logger.exception("[Router] ❌ LLM routing failed")
            raise
        
        destinations = get_routing_destinations(decision.intent)

        elapsed = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[Router] ✅ Decision: {decision.intent} | Tools: {decision.required_tools} | Latency: {elapsed}ms"
        )

        return Command(
            goto=destinations,
            update={
                "required_tools": decision.required_tools,
                "iteration_count": current_iteration + 1
            }
        )

    return router