from enum import StrEnum

from langgraph.graph import END, START


class AgentGraphNode(StrEnum):
    START_NODE = START

    INPUT_ANALYZER = "input_analyzer"
    PLANNER = "planner" 
    REPLANNER = "replanner"
    ROUTER = "router"             # (Now acts as a Step Dispatcher)
    RAG = "rag"
    WEB_SEARCH = "web_search"
    TOOL = "tool"
    ENRICHMENT = "enrichment"
    SYNTHESIZER = "synthesizer"
    SUMMARIZER = "summarizer"

    END_NODE = END