# A simple set to hold the names of our trusted tools
from enum import StrEnum
from typing import Dict, Optional

from pydantic import BaseModel, Field

from app.core.tools.registry.ingestion_config_tool import IngestionConfig, IngestionConfidenceTier
from app.core.vector_store.vector_store import VectorStoreType


KNOWLEDGE_GRAPH_TOOL_REGISTRY: Dict[str, IngestionConfig] = {}

def ingestion_to_persistence_layer(
    vector_store_type: VectorStoreType, 
    ingestion_confidence_tier: IngestionConfidenceTier,
    source_type_label: Optional[str] = None,
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
        final_label = source_type_label if source_type_label else langchain_tool.name
        
        KNOWLEDGE_GRAPH_TOOL_REGISTRY[langchain_tool.name] = IngestionConfig(
           vector_store_type=vector_store_type,
           ingestion_confidence_tier=ingestion_confidence_tier,
           source_type_label=final_label,
           skip_relevance_check=skip_relevance_check
        )
        return langchain_tool
    return decorator