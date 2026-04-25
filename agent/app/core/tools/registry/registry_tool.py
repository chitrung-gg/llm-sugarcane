# A simple set to hold the names of our trusted tools
from enum import StrEnum
from typing import Dict, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from app.schemas.knowledge.knowledge_ingestion_schema import IngestionConfidenceTier, IngestionSourceType
from app.core.tools.registry.ingestion_config_tool import IngestionConfig
from app.core.vector_store.vector_store import VectorStoreType


KNOWLEDGE_GRAPH_TOOL_REGISTRY: Dict[str, IngestionConfig] = {}
_AGENT_TOOLS: Dict[str, BaseTool] = {}

def ingestion_to_persistence_layer(
    vector_store_type: VectorStoreType, 
    ingestion_confidence_tier: IngestionConfidenceTier,
    source_type_label: IngestionSourceType,
    skip_relevance_check: bool = False
):
    """
        Decorator to register a tool for ingestion to persistence layer based on the config.

        Args:
            vector_store_type (VectorStoreType): The type of vector store where the data should be ingested.
            ingestion_confidence_tier (IngestionConfidenceTier): The trust/confidence level assigned to data from this tool.
            source_type_label (Optional[str], optional): An optional label for the source type. Defaults to the tool's name if not provided.
            skip_relevance_check (bool, optional): If True, bypasses the domain relevance check during ingestion. Defaults to False.

        Returns:
            Callable: A decorator that registers the tool with the specified ingestion configuration into KNOWLEDGE_GRAPH_TOOL_REGISTRY.
    """
    
    def decorator(langchain_tool):
        KNOWLEDGE_GRAPH_TOOL_REGISTRY[langchain_tool.name] = IngestionConfig(
           vector_store_type=vector_store_type,
           ingestion_confidence_tier=ingestion_confidence_tier,
           source_type_label=source_type_label,
           skip_relevance_check=skip_relevance_check
        )
        return langchain_tool
    return decorator

def register_agent_tool(tool_instance: BaseTool):
    """Registers a tool instance into the global agent registry."""
    _AGENT_TOOLS[tool_instance.name] = tool_instance
    return tool_instance

def get_agent_tools() -> Dict[str, BaseTool]:
    """Retrieves all registered tools for the agent."""
    return _AGENT_TOOLS