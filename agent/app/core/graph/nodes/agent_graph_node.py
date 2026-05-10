from enum import StrEnum

from langgraph.graph import END, START


class AgentGraphNode(StrEnum):
    START_NODE = START
    END_NODE = END

    # --- Inner Graph Nodes (ReAct Loop) ---
    INPUT_ANALYZER = "input_analyzer"
    ROUTER = "router"
    RAG = "rag"
    WEB_SEARCH = "web_search"
    TOOL = "tool"
    ENRICHMENT = "enrichment"
    INNER_SYNTHESIZER = "inner_synthesizer"

    # --- Outer Graph Nodes (Plan & Execute Loop) ---
    PLANNER = "planner"
    HUMAN_REVIEW = "human_review"
    EXECUTOR = "executor"
    SUMMARIZER = "summarizer"
    OUTER_SYNTHESIZER = "outer_synthesizer"
    # REPLANNER = "replanner"