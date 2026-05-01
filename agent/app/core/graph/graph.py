from enum import StrEnum

from langchain_qdrant import QdrantVectorStore
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from langchain_core.tools import BaseTool
from loguru import logger


from app.core.graph.nodes.components.executor_node import make_executor_node
from app.core.graph.nodes.components.planner_node import make_planner_node
from app.core.graph.nodes.components.replanner_node import make_replanner_node
from app.core.graph.nodes.agent_planner import PlanExecuteState
from app.core.tools.registry.registry_tool import KNOWLEDGE_GRAPH_TOOL_REGISTRY
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.nodes.components.summarizer_node import make_summarizer_node
from app.core.graph.nodes.components.input_analyzer_node import make_input_analyzer_node
from app.utils.document_processor import DocumentProcessor
from app.core.graph.nodes.components.web_search_node import make_web_search_node
from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.components.rag_node import make_rag_node

from app.core.graph.nodes.components.router_node import make_router_node
from app.core.graph.nodes.components.synthesizer_node import make_synthesizer_node
from app.core.graph.nodes.components.tools_node import make_tools_node
from app.core.graph.nodes.components.enrichment_node import make_enrichment_node
from app.core.graph.state.agent_state import AgentState
from app.configs.storage.databases import langgraph_connection_pool

from app.services.ingestion.graph_ingestion_service import GraphIngestionService

async def build_super_agent_graph(
    llm_service: LLMService,
    vector_store_solid: QdrantVectorStore,
    vector_store_volatile: QdrantVectorStore,
    searx_wrapper: SearxSearchWrapper,
    document_processor: DocumentProcessor, 
    graph_ingestion_service: GraphIngestionService,
    available_tools: dict[str, BaseTool]
):
    # 1. Build the INNER ReAct Graph exactly as it is today
    inner_react_graph = await _build_agent_graph(
        llm_service=llm_service,
        vector_store_solid=vector_store_solid,
        vector_store_volatile=vector_store_volatile,
        searx_wrapper=searx_wrapper,
        document_processor=document_processor,
        graph_ingestion_service=graph_ingestion_service,
        available_tools=available_tools
    )

    # 2. Initialize the OUTER Plan-and-Execute Graph
    workflow = StateGraph(PlanExecuteState)

    # 3. Add the 3 Outer Nodes using the StrEnum
    workflow.add_node(AgentGraphNode.PLANNER, make_planner_node(llm_service))
    workflow.add_node(AgentGraphNode.EXECUTOR, make_executor_node(inner_react_graph))
    workflow.add_node(AgentGraphNode.REPLANNER, make_replanner_node(llm_service))

    # 4. Define the simple entry point
    workflow.add_edge(AgentGraphNode.START_NODE, AgentGraphNode.PLANNER)
    
    # NOTE: The nodes handle all other routing internally using Command(goto=...)!

    # 5. Attach Checkpointer (Short-term Memory)
    checkpointer = AsyncPostgresSaver(langgraph_connection_pool)
    await checkpointer.setup()

    # 6. Attach Store (Long-term Memory)
    store = AsyncPostgresStore(langgraph_connection_pool)
    await store.setup()

    graph = workflow.compile(
        checkpointer=checkpointer,
        store=store
    )
    logger.debug("\n" + graph.get_graph().draw_mermaid())
    
    return graph

async def _build_agent_graph(
    llm_service: LLMService,
    vector_store_solid: QdrantVectorStore,
    vector_store_volatile: QdrantVectorStore,
    searx_wrapper: SearxSearchWrapper,
    document_processor: DocumentProcessor, 
    graph_ingestion_service: GraphIngestionService,
    available_tools: dict[str, BaseTool]
):
    # Initialize graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node(
        AgentGraphNode.INPUT_ANALYZER,
        make_input_analyzer_node(document_processor),
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0)
    )
    workflow.add_node(
        AgentGraphNode.ROUTER,
        make_router_node(llm_service, available_tools)
    )
    workflow.add_node(
        AgentGraphNode.RAG,
        make_rag_node(vector_store_solid, vector_store_volatile, llm_service)
    )
    workflow.add_node(
        AgentGraphNode.WEB_SEARCH,
        make_web_search_node(searx_wrapper, llm_service)
    )
    workflow.add_node(
        AgentGraphNode.TOOL,
        make_tools_node(available_tools)
    )
    workflow.add_node(
        AgentGraphNode.ENRICHMENT,
        make_enrichment_node(KNOWLEDGE_GRAPH_TOOL_REGISTRY)
    )
    workflow.add_node(
        AgentGraphNode.SYNTHESIZER,
        make_synthesizer_node(llm_service, available_tools)
    )
    workflow.add_node(
        AgentGraphNode.SUMMARIZER,
        make_summarizer_node(llm_service)
    )

    # Define flows
    workflow.add_edge(START, AgentGraphNode.INPUT_ANALYZER)
    # workflow.add_edge("input_analyzer", "router")

    # Conditional Routing
    # workflow.add_conditional_edges(
    #     "router",
    #     route_action,
    #     {
    #         # Name returned by route_action : Name of next node to visit 
    #         "rag_execution": "rag_execution",
    #         "tool_execution": "tool_execution",
    #         "web_search": "web_search",
    #         "synthesizer": "synthesizer"
    #     }
    # )

    # workflow.add_conditional_edges(
    #     "rag_execution",
    #     check_rag_fallback,
    #     {
    #         # Name returned by route_action : Name of next node to visit
    #         "web_search": "web_search",
    #         "synthesizer": "synthesizer"
    #     }
    # )

    # Merge results
    # workflow.add_edge("tool_execution", "synthesizer")
    # workflow.add_edge("web_search", "synthesizer")

    # Check if answer appropriate
    # workflow.add_conditional_edges(
    #     "synthesizer",
    #     check_if_resolved,
    #     {
    #         END: END,
    #         "router": "router"
    #     }
    # )

    # # Utilize Checkpoint to save State
    # checkpointer = AsyncPostgresSaver(langgraph_connection_pool)
    # await checkpointer.setup()

    # graph = workflow.compile(
    #     checkpointer=checkpointer
    # )
    graph = workflow.compile()
    logger.debug("\n" + graph.get_graph().draw_mermaid())
    return graph