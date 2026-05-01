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
    SYNTHESIZER = "synthesizer"
    SUMMARIZER = "summarizer"

    # --- Outer Graph Nodes (Plan & Execute Loop) ---
    PLANNER = "planner"
    EXECUTOR = "executor"
    REPLANNER = "replanner"