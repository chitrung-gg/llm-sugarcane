from enum import StrEnum

from langchain_qdrant import QdrantVectorStore
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from langchain_core.tools import BaseTool
from loguru import logger


from app.core.graph.nodes.components.outer_synthesizer_node import make_outer_synthesizer_node
from app.utils.graph.context_utils import format_tools_for_prompt
from app.core.graph.nodes.components.human_review_node import make_human_review_node
from app.core.graph.nodes.components.executor_node import make_executor_node
from app.core.graph.nodes.components.planner_node import make_planner_node
# from app.core.graph.nodes.components.replanner_node import make_replanner_node
from app.core.graph.state.planner_state import PlanExecuteState
from app.core.tools.registry.registry_tool import KNOWLEDGE_GRAPH_TOOL_REGISTRY
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.nodes.components.summarizer_node import make_summarizer_node
from app.core.graph.nodes.components.input_analyzer_node import make_input_analyzer_node
from app.utils.document_processor import DocumentProcessor
from app.core.graph.nodes.components.web_search_node import make_web_search_node
from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.components.rag_node import make_rag_node

from app.core.graph.nodes.components.router_node import make_router_node
from app.core.graph.nodes.components.inner_synthesizer_node import make_inner_synthesizer_node
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
    # graph_ingestion_service: GraphIngestionService,
    available_tools: dict[str, BaseTool]
):
    # 1. Build the INNER ReAct Graph exactly as it is today
    inner_react_graph = await _build_agent_graph(
        llm_service=llm_service,
        vector_store_solid=vector_store_solid,
        vector_store_volatile=vector_store_volatile,
        searx_wrapper=searx_wrapper,
        document_processor=document_processor,
        # graph_ingestion_service=graph_ingestion_service,
        available_tools=available_tools
    )

    planner_tools_str = format_tools_for_prompt(
        available_tools, 
        include_description=True, 
        include_params=False
    )

    inner_agent_capabilities = [
        "Semantic Search (RAG): Automatically search Vector Databases (Qdrant) and Knowledge Graphs (Neo4j) for literature, trait-gene associations, and general bioinformatics knowledge.",
        "Web Search: Search the internet for current events, updated papers, or general knowledge."
    ]
    
    # Only append the tool capability if tools actually exist
    if planner_tools_str.strip():
        inner_agent_capabilities.append(
            f"Tool Execution: Execute specialized bioinformatics tools. The current specialized tools available are:\n{planner_tools_str}"
        )

    # 2. Initialize the OUTER Plan-and-Execute Graph
    workflow = StateGraph(PlanExecuteState)

    # 3. Add the 3 Outer Nodes using the StrEnum
    workflow.add_node(AgentGraphNode.PLANNER, make_planner_node(llm_service, inner_agent_capabilities))
    workflow.add_node(AgentGraphNode.EXECUTOR, make_executor_node(inner_react_graph))
    # workflow.add_node(AgentGraphNode.REPLANNER, make_replanner_node(llm_service))
    workflow.add_node(AgentGraphNode.HUMAN_REVIEW, make_human_review_node())
    workflow.add_node(AgentGraphNode.OUTER_SYNTHESIZER, make_outer_synthesizer_node(llm_service))
    workflow.add_node(AgentGraphNode.SUMMARIZER, make_summarizer_node(llm_service))

    # 4. Define Architectural Blueprint Edges
    workflow.add_edge(START, AgentGraphNode.PLANNER)
    # workflow.add_edge(AgentGraphNode.PLANNER, AgentGraphNode.EXECUTOR) - Using Command
    # workflow.add_edge(AgentGraphNode.EXECUTOR, AgentGraphNode.REPLANNER) - Using Command
    # workflow.add_edge(AgentGraphNode.REPLANNER, AgentGraphNode.EXECUTOR) - Using Command # Loop for more steps
    # workflow.add_edge(AgentGraphNode.REPLANNER, END) - Using Command # Finish conversation
    
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
    # graph_ingestion_service: GraphIngestionService,
    available_tools: dict[str, BaseTool]
):
    # Initialize graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node(
        AgentGraphNode.INPUT_ANALYZER,
        make_input_analyzer_node(document_processor, llm_service),
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
        AgentGraphNode.INNER_SYNTHESIZER,
        make_inner_synthesizer_node(llm_service, available_tools)
    )
    
    # 1. Entry Point
    workflow.add_edge(START, AgentGraphNode.INPUT_ANALYZER)
    # workflow.add_edge(AgentGraphNode.INPUT_ANALYZER, AgentGraphNode.ROUTER)
    
    # # 2. Router Fan-out (Allowed destinations)
    # workflow.add_edge(AgentGraphNode.ROUTER, AgentGraphNode.RAG)
    # workflow.add_edge(AgentGraphNode.ROUTER, AgentGraphNode.TOOL)
    # workflow.add_edge(AgentGraphNode.ROUTER, AgentGraphNode.WEB_SEARCH)
    # workflow.add_edge(AgentGraphNode.ROUTER, AgentGraphNode.SYNTHESIZER)
    
    # # 3. Execution Branches converge on Synthesizer (Fan-in pattern)
    # workflow.add_edge(AgentGraphNode.RAG, AgentGraphNode.SYNTHESIZER)
    # workflow.add_edge(AgentGraphNode.TOOL, AgentGraphNode.ENRICHMENT)
    # workflow.add_edge(AgentGraphNode.ENRICHMENT, AgentGraphNode.SYNTHESIZER)
    # workflow.add_edge(AgentGraphNode.WEB_SEARCH, AgentGraphNode.SYNTHESIZER)
    
    # # 4. Synthesis and Feedback Loop
    # workflow.add_edge(AgentGraphNode.SYNTHESIZER, AgentGraphNode.SUMMARIZER)
    # workflow.add_edge(AgentGraphNode.SYNTHESIZER, AgentGraphNode.ROUTER) # Loop-back for incomplete answers
    
    # # 5. Exit Path
    # workflow.add_edge(AgentGraphNode.SUMMARIZER, AgentGraphNode.END_NODE)

    graph = workflow.compile()
    logger.debug("\n" + graph.get_graph().draw_mermaid())
    return graph