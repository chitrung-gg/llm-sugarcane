from langchain_qdrant import QdrantVectorStore
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from loguru import logger


from app.core.graph.nodes.input_analyzer_node import make_input_analyzer_node
from app.utils.document_processor import DocumentProcessor
from app.core.graph.routing.check_rag_fallback import check_rag_fallback
from app.core.graph.nodes.web_search_node import make_web_search_node
from app.services.llm.llm_service import LLMService
from app.core.graph.nodes.rag_node import make_rag_node

from app.core.graph.nodes.router_node import make_router_node
from app.core.graph.nodes.synthesizer_node import make_synthesizer_node
from app.core.graph.nodes.tools_node import tools
from app.core.graph.routing.check_if_resolved import check_if_resolved
from app.core.graph.state.agent_state import AgentState


def build_agent_graph(
    llm_service: LLMService,
    vector_store: QdrantVectorStore,
    searx_wrapper: SearxSearchWrapper,
    document_processor: DocumentProcessor
):
    # Initialize graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node(
        "input_analyzer",
        make_input_analyzer_node(document_processor),
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0)
    )
    workflow.add_node(
        "router",
        make_router_node(llm_service)
    )
    workflow.add_node(
        "rag_execution",
        make_rag_node(vector_store)
    )
    workflow.add_node(
        "web_search",
        make_web_search_node(searx_wrapper)
    )
    workflow.add_node(
        "tool_execution",
        tools
    )
    workflow.add_node(
        "synthesizer",
        make_synthesizer_node(llm_service)
    )

    # Define flows
    workflow.add_edge(START, "input_analyzer")
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

    graph = workflow.compile()
    logger.debug(graph.get_graph().draw_ascii())
    return graph