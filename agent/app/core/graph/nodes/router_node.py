import time
from typing import Literal, Union
from loguru import logger

from app.core.graph.nodes.tools_node import AVAILABLE_TOOLS
from app.core.graph.routing.route_action import RouteDecision, get_routing_destinations
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import render_text_description_and_args
from langgraph.types import Command

after_router_node = Literal["rag_execution", "tool_execution", "web_search", "synthesizer"]

def make_router_node(llm_service: LLMService):
    async def router(state: AgentState) -> Command[after_router_node]:
        logger.debug("[Router] 🧭 Starting intent analysis")

        start_time = time.time()

        query = state["query"]
        logger.debug(f"[Router] Query: {query}")

        llm = llm_service.get_secondary_model()
        router_llm = llm.with_structured_output(RouteDecision)

        tool_list_str = render_text_description_and_args(list(AVAILABLE_TOOLS.values()))

        # executed_tools = state.get("tool_results", [])
        # if executed_tools:
        #     executed_str = render_text_description_and_args(executed_tools)
        #     tool_history_prompt = f"""
        #         \nPREVIOUSLY EXECUTED TOOLS:\nYou have already run these tools: \n{executed_str}\nDO NOT run them again unless absolutely necessary. Look at the missing information and pick the NEXT logical tool in the chain.
        #     """
        # else:
        #     tool_history_prompt = ""
        
        system_instructions = f"""
            You are an expert routing assistant for a Sugarcane Genomics system.
            Your job is to analyze the user's query and route it to the correct execution path.

            CRITICAL ROUTING RULES:
            - Choose 'direct_answer': If the user asks to summarize, translate, or answer questions strictly about a file they just uploaded, and you can see the file's content in the chat history.
            - Choose 'all' (RECOMMENDED DEFAULT): For general sugarcane biology questions.
            - Choose 'web_search': For the *latest* news, external web data, or broad scientific facts.
            - Choose 'rag_only': ONLY if the query explicitly targets our internal database.
            - Choose 'tool_only': For executing bioinformatic tools (BLAST/Synteny).
            - Choose 'unclear': For simple greetings.

            AVAILABLE BIOINFORMATICS TOOLS:
            {tool_list_str}
            
            
            CRITICAL: If you decide tools are required, you MUST use the exact tool names listed above. Do not guess or invent tool names and arguments.
        """
        
        user_input = f"User Query: {query}"

        messages_to_send = [
            SystemMessage(content=system_instructions),
            HumanMessage(content=user_input),
        ]

        # Include previous chat history if it exists
        if state.get("messages"):
            history_messages = state["messages"]
            logger.debug(
                f"[Router] Including chat history | total_messages={len(history_messages)}"
            )
            
            # 1. Extract up to the last 5 messages
            last_5_msgs = history_messages[-5:]
            
            logger.debug("[Router] --- Last 5 Messages in Context ---")
            for idx, msg in enumerate(last_5_msgs):
                # Identify if it is a HumanMessage, AIMessage, etc.
                msg_type = msg.__class__.__name__ 
                
                # Truncate the content to 150 characters for clean terminal output
                raw_content = str(msg.content).replace("\n", " ")
                content_preview = raw_content[:150] + ("..." if len(raw_content) > 150 else "")
                
                logger.debug(f"  {idx + 1}. [{msg_type}]: {content_preview}")
            logger.debug("--------------------------------------------")

            # 2. Append the history to the prompt
            # Pro-tip: If conversations get very long, you might want to change this to:
            # messages_to_send.extend(history_messages[-10:]) 
            # to prevent the Router from exceeding its context window!
            messages_to_send.extend(history_messages)
        
        logger.debug(
            f"[Router] Sending {len(messages_to_send)} messages to LLM"
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
            f"[Router] ✅ Decision made | "
            f"intent={decision.intent} | "
            f"tools={decision.required_tools} | "
            f"latency={elapsed}ms"
        )

        return Command(
            goto=destinations,
            update={
                "required_tools": decision.required_tools
            }
        )

    return router