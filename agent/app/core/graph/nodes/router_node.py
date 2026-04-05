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

        start_time = time.time()

        query = state["query"]
        logger.debug(f"[Router] Query: {query}")

        llm = llm_service.get_secondary_model()
        router_llm = llm.with_structured_output(RouteDecision)

        tool_list_str = render_text_description_and_args(list(available_tools.values()))

        rag_results = state.get("rag_results", [])
        tool_results = state.get("tool_results", [])
        web_results = state.get("web_results", [])

        execution_history = ""
        if rag_results or tool_results or web_results:
            execution_history += "\n--- CURRENT SEARCH/TOOL RESULTS ---\n"
            if rag_results:
                execution_history += f"- Found {len(rag_results)} chunks from local RAG.\n"
            if tool_results:
                execution_history += "- Tool History:\n"
                for res in tool_results:
                    status_emoji = "✅" if res['status'] == "success" else "❌"
                    execution_history += f"  {status_emoji} {res['tool_name']}: {res['output'][:300]}...\n"
            if web_results:
                execution_history += f"- Found {len(web_results)} web results.\n"
            
            execution_history += """
                1. If the results above are SUFFICIENT to fully answer the user, choose 'direct_answer' to finish.
                2. If a tool returned 'Unknown', 'Error', or generic metadata (like 'GCA_...' without names), DO NOT repeat it. Instead, try a different tool (e.g., if genome search failed, try gene search or web search).
                3. If you have partial info, decide which specific tool can fill the remaining gap.
            """

        
        system_instructions = f"""
            You are an expert routing assistant for a Sugarcane Genomics system.
            Your job is to analyze the user's query and route it to the correct execution path.

            {execution_history}

            CRITICAL ROUTING RULES:
            - Choose 'direct_answer': If you have enough information to answer, or if the user asks a simple question (about uploaded files or not).
            - Choose 'all' (RECOMMENDED FOR FIRST TURN): For general biological queries.
            - Choose 'web_search': For latest news or when internal databases (RAG/Tools) fail.
            - Choose 'rag_only': For queries specifically about local documents.
            - Choose 'tool_only': For specialized bioinformatic analyses (NCBI, BLAST, etc.)

            AVAILABLE BIOINFORMATICS TOOLS:
            {tool_list_str}
            
            
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
            messages_to_send.extend(state["messages"])
        
        logger.debug(
            f"[Router] Sending {len(messages_to_send)} messages to LLM (Iteration: {state.get('iteration_count', 0)})"
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
                "required_tools": decision.required_tools
            }
        )

    return router