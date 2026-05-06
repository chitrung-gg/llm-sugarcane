import time
from typing import List, Literal, Union, cast
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

        # Tier 2 (Secondary - Flash) for fast but reliable routing
        router_llm = llm_service.get_structured_secondary_model(RouteDecision)
        tool_list_str = render_text_description_and_args(list(available_tools.values()))

        # 1. Dynamic Intents Builder
        rag_results = state.get("rag_results", [])
        tool_results = state.get("tool_results", [])
        web_results = state.get("web_results", [])

        available_intents_list = [
            "- 'direct_answer': Use ONLY when the answer is complete OR no further improvement is possible.",
            "- 'all': Use this to run local document RAG *AND* Bioinformatics/Knowledge Graph tools simultaneously. Best for comprehensive research.",
            "- 'tool_only': For specialized bioinformatics analysis OR searching the Knowledge Graph."
        ]
        
        if not web_results:
            available_intents_list.append("- 'web_search': For latest or external information.")
        if not rag_results:
            available_intents_list.append("- 'rag_only': For reading, extracting, analyzing, or summarizing content from local documents (e.g., PDFs) in the user's workspace.")
        
        intents_str = "\n".join(available_intents_list)

        # 2. ReAct prompts for fail-fast
        execution_history = ""
        failed_tools = []
        
        if rag_results or tool_results or web_results:
            if rag_results:
                rag_preview = str(rag_results)[:settings.ROUTER_MAX_RAG_RESULTS_LENGTH] + "..."
                execution_history += f"<executed_action type='rag_only'>\n  <preview>{rag_preview}</preview>\n</executed_action>\n"
            
            if web_results:
                web_preview = str(web_results)[:settings.ROUTER_MAX_WEB_RESULTS_LENGTH] + "..."
                execution_history += f"<executed_action type='web_search'>\n  <preview>{web_preview}</preview>\n</executed_action>\n"

            if tool_results:
                for res in tool_results:
                    if res['status'] == "error":
                        failed_tools.append(res['tool_name'])
                    execution_history += f"<executed_tool name='{res['tool_name']}' status='{res['status']}'>\n  <args>{res.get('args', {})}</args>\n  <output>{res['output'][:settings.ROUTER_MAX_TOOL_RESULTS_LENGTH]}...</output>\n</executed_tool>\n"

        if not execution_history:
            execution_history = "<info>No actions executed yet in this loop.</info>"

        failover_instruction = ""
        if failed_tools:
            failover_instruction = f"<failed_tools>{', '.join(set(failed_tools))}</failed_tools>"
        else:
            failover_instruction = "<info>No failed tools to report.</info>"

        # 3. Build the Dynamic Workspace Context
        active_project = state.get("active_project")
        active_datasets = state.get("active_datasets", [])
        p_name = active_project.get("project_name", "Default Project") if active_project else "Default Project"
        
        if not active_datasets:
            workspace_str = f"<project name='{p_name}' />\n<datasets status='empty' />"
        else:
            blocks = [f"<project name='{p_name}'>"]
            for ds in active_datasets:
                blocks.append(f"  <dataset id='{ds.get('dataset_id')}' name='{ds.get('dataset_name')}' source='{ds.get('source')}'>")
                
                # Genomic Files
                for f in ds.get("genomic_files", []):
                    blocks.append(f"    <file type='{f.get('file_type')}' id='{f.get('file_id')}' category='GENOMIC'>{f.get('file_name')}</file>")
                
                # Knowledge Files
                for f in ds.get("knowledge_files", []):
                    blocks.append(f"    <file type='{f.get('file_type')}' id='{f.get('file_id')}' category='KNOWLEDGE'>{f.get('file_name')}</file>")
                
                blocks.append("  </dataset>")
            blocks.append("</project>")
            workspace_str = "\n".join(blocks)

        # 4. Format the Base System Instructions
        # Format the top-level instructions
        sys_msg_1 = ROUTER_SYSTEM_INSTRUCTIONS.format(
            workspace_context=workspace_str,
            extracted_knowledge=str(state.get("extracted_knowledge", [])),
            tool_list_str=tool_list_str,
            conversation_summary=state.get('summary', 'No summary available yet.')
        )

        messages_to_send: List[BaseMessage] = [
            SystemMessage(content=sys_msg_1),
            HumanMessage(content=f"User Query: {query}")
        ]
        
        # Format the bottom-level enforcement constraints
        sys_msg_2 = ROUTER_FINAL_STATE_ENFORCEMENT.format(
            execution_history=execution_history,
            failover_instruction=failover_instruction,
            intents_str=intents_str
        )
        messages_to_send.append(SystemMessage(content=sys_msg_2))
        
        logger.debug(f"[Router] Sending {len(messages_to_send)} messages to LLM")

        # 5. Execute
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
                "rag_query": decision.rag_query,
                "web_query": decision.web_query,
                "iteration_count": current_iteration + 1,
                "last_intent": decision.intent,
                "router_guidance": decision.reasoning
            }
        )

    return router