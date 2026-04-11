# A simple set to hold the names of our trusted tools
TRUSTED_KNOWLEDGE_GRAPH_TOOLS = set()

def ingest_to_knowledge_graph(langchain_tool):
    """
    Decorator to auto-register a LangChain tool for Knowledge Graph ingestion.

    Only these tools results are allowed to write to the Knowledge Graph
    """
    TRUSTED_KNOWLEDGE_GRAPH_TOOLS.add(langchain_tool.name)
    return langchain_tool