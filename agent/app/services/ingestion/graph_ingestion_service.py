import json
import uuid
import asyncio
from typing import List, Dict, LiteralString, Optional, Any, cast
from langchain_neo4j import Neo4jGraph
from loguru import logger
from pydantic import BaseModel, Field

from app.core.prompts.graph_ingestion_prompts import EXTRACTION_PROMPT
from app.core.tools.registry.ingestion_config_tool import IngestionConfig
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionConfidenceTier, IngestionSourceType
from app.core.tools.registry.registry_tool import KNOWLEDGE_GRAPH_TOOL_REGISTRY
from app.core.vector_store.vector_store import VectorStoreType
from app.schemas.graph.knowledge_graph_schema import KnowledgeGraphComponents
from app.services.llm.llm_service import LLMService
from app.configs.storage.databases import genome_connection_pool
from langchain_qdrant import QdrantVectorStore
from langchain_neo4j.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document


class GraphIngestionService:
    def __init__(
        self,
        llm_service: LLMService,
        knowledge_graph: Neo4jGraph,
        vector_store_solid: QdrantVectorStore,
        vector_store_volatile: QdrantVectorStore
    ):
        self.llm_service = llm_service
        self.knowledge_graph = knowledge_graph
        self.vector_store_solid = vector_store_solid
        self.vector_store_volatile = vector_store_volatile
        self.allowed_labels = {"Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"}

    async def extract_components(self, text: str) -> KnowledgeGraphComponents:
        prompt = EXTRACTION_PROMPT.format(text=text)
        model = self.llm_service.get_structured_secondary_model(KnowledgeGraphComponents)
        result = await model.ainvoke(prompt)
        return cast(KnowledgeGraphComponents, result)

    async def ingest_knowledge(
        self,
        source_text: str, 
        source_metadata: Optional[Dict[str, Any]] = None,
        project_name: Optional[str] = None
    ):
        try:
            source_meta = source_metadata or {}
            tool_name = source_meta.get("tool", "unknown")

            # 1. Fetch Tool Configuration
            tool_config = KNOWLEDGE_GRAPH_TOOL_REGISTRY.get(tool_name)
            if not tool_config:
                logger.info(f"Source '{tool_name}' not in registry. Defaulting to general text ingestion.")
                # We dynamically construct a config for unstructured/unregistered text
                # Make sure the Enum values match your IngestionSourceType/IngestionConfidenceTier schemas
                tool_config = IngestionConfig(
                    vector_store_type=VectorStoreType.SOLID, 
                    source_type_label=IngestionSourceType.CURATED_DOCUMENT, # Or GENERAL_TEXT depending on your schema
                    ingestion_confidence_tier=IngestionConfidenceTier.INFERRED, # Baseline trust for unregistered sources
                    skip_relevance_check=False # Forces the LLM to strictly evaluate relevance
                )

            # Fast-fail: Do not ingest tool error messages or "not found" results.
            # This saves LLM tokens and prevents garbage data in your databases.
            text_lower = source_text.strip().lower()
            if not self._is_ingestable_payload(source_text):
                logger.debug(f"Graph Ingestion Aborted: Output from {tool_name} failed heuristic checks (likely a tool error or empty result).")
                return
            
            # 2. Extract Data via LLM
            components = await self.extract_components(source_text)

            # 3. Validation & The "Confidence Circuit Breaker"
            if not tool_config.skip_relevance_check and not components.is_domain_relevant:
                logger.warning(f"Ingestion Aborted: Output from {tool_name} is not domain relevant.")
                return
            
            # 3.1. USE LLM CONFIDENCE: If the text is pure garbage, abort to save DB space
            if components.overall_confidence < 0.4:
                logger.warning(f"Ingestion Aborted: LLM Overall Confidence too low ({components.overall_confidence}).")
                return
                
            if not components.nodes:
                logger.debug("Graph Ingestion Aborted: No valid nodes extracted.")
                return
            
            # 4. Route to the Correct Vector Store
            target_vector_store = None
            if tool_config.vector_store_type == VectorStoreType.SOLID:
                target_vector_store = self.vector_store_solid
            elif tool_config.vector_store_type == VectorStoreType.VOLATILE:
                target_vector_store = self.vector_store_volatile
            else:
                logger.error("The vector store type has not been configured.")
                return

            node_registry = {}

            # 5. Save to PostgreSQL
            logger.info("Saving to PostgreSQL...")
            async with genome_connection_pool.connection() as conn:
                for node in components.nodes:
                    if node.label not in self.allowed_labels:
                        continue
                        
                    global_id = uuid.uuid4()
                    node_registry[node.name] = {"id": global_id, "label": node.label}
                    
                    # Construct metadata JSON
                    meta_payload = json.dumps({
                        "description": node.description,
                        "aliases": node.aliases,
                        "recent_source": source_meta,
                        "llm_overall_confidence": components.overall_confidence # Track it in Postgres!
                    })
                    
                    # Upsert Postgres: || operator merges JSONB, retaining old keys while updating new ones
                    await conn.execute(
                        """
                        INSERT INTO knowledge_entities (global_id, name, entity_type, knowledge_entities_metadata)
                        VALUES (%s, %s, %s, %s::jsonb)
                        ON CONFLICT (name) DO UPDATE 
                        SET entity_type = EXCLUDED.entity_type,
                            knowledge_entities_metadata = COALESCE(knowledge_entities.knowledge_entities_metadata, '{}'::jsonb) || EXCLUDED.knowledge_entities_metadata
                        RETURNING global_id
                        """,
                        (global_id, node.name, node.label, meta_payload)
                    )

            # 6. Save to Neo4j
            logger.info("Saving to Neo4j safely via LangChain...")
            # 6.1. Convert your custom Pydantic Nodes into LangChain Nodes
            langchain_nodes = {}
            for node in components.nodes:
                if node.name in node_registry:
                    node_info = node_registry[node.name]
                    
                    # Langchain's Node safely escapes labels and properties
                    lc_node = Node(
                        id=node.name, # Primary match key
                        type=node_info['label'], 
                        properties={
                            "global_id": str(node_info['id']), # Syncs with Postgres/Qdrant
                            "description": node.description
                        }
                    )
                    langchain_nodes[node.name] = lc_node

            # 6.2. Convert your custom Pydantic Relationships into LangChain Relationships
            langchain_rels = []
            for rel in components.relationships:
                # Filter out weak relationships right at the edge!
                if rel.confidence < 0.4:
                    logger.debug(f"Skipping weak relationship: {rel.source_name} -> {rel.target_name} (Conf: {rel.confidence})")
                    continue

                if rel.source_name in langchain_nodes and rel.target_name in langchain_nodes:
                    source_node = langchain_nodes[rel.source_name]
                    target_node = langchain_nodes[rel.target_name]
                    
                    # LangChain safely sanitizes the relationship type
                    safe_type = rel.type.strip().upper().replace(" ", "_").replace("-", "_")
                    
                    lc_rel = Relationship(
                        source=source_node,
                        target=target_node,
                        type=safe_type,
                        properties={
                            "evidence": rel.evidence,
                            "context": rel.context,
                            "confidence": rel.confidence,  # The Semantic Trust (From LLM)
                            "source_type": tool_config.source_type_label, 
                            "source_tier": tool_config.ingestion_confidence_tier.value, # The Structural Trust
                            "tool_used": tool_name
                        }
                    )
                    langchain_rels.append(lc_rel)

            # 6.3. Create a GraphDocument and let LangChain handle the complex MERGE logic!
            if langchain_rels:
                graph_document = GraphDocument(
                    nodes=list(langchain_nodes.values()),
                    relationships=langchain_rels,
                    source=Document(page_content=source_text) # Keeps track of where this came from
                )

                # This single line safely upserts the nodes and relationships into Neo4j
                await asyncio.to_thread(
                    self.knowledge_graph.add_graph_documents,
                    [graph_document],
                    baseEntityLabel=True
                )
            
            # 7. Save to Qdrant
            logger.info("Saving to Qdrant...")
            documents, metadatas, ids = [], [], []
            for node in components.nodes:
                if node.name in node_registry:
                    node_info = node_registry[node.name]
                    text_to_embed = f"{node.name} is a {node_info['label']}. Description: {node.description or 'None'}. Context: {source_text[:200]}..."
                    
                    documents.append(text_to_embed)
                    metadatas.append({
                        "global_id": str(node_info['id']), # Matches Postgres and Neo4j perfectly
                        "entity_type": node_info['label'], 
                        "name": node.name,
                        "project_name": project_name,
                        "source_tier": tool_config.ingestion_confidence_tier.value,
                        "tool_used": tool_name,
                        "llm_confidence": components.overall_confidence # Track it in Qdrant!
                    })
                    ids.append(str(node_info['id'])) # Qdrant accepts string UUIDs natively
                    
            if documents:
                await target_vector_store.aadd_texts(texts=documents, metadatas=metadatas, ids=ids)
                
            logger.info(f"Graph ingestion complete: {len(components.nodes)} nodes, {len(components.relationships)} relationships.")
            
        except Exception as e:
            logger.error("Graph ingestion failed: {e}", e=e)
            raise e
        
    def _is_ingestable_payload(self, text: str) -> bool:
        """
        Fast-fail heuristic to prevent sending tool error messages or empty strings to the LLM.
        Saves tokens by filtering out obvious non-data before the LLM extraction step.
        """
        clean_text = text.strip()
        
        # 1. Minimum Length Check (Too short to contain valid biological relationships)
        if len(clean_text) < 30:
            return False
            
        # 2. Tool Failure Prefix Check
        # We also catch standard Python/system error prefixes.
        text_lower = clean_text.lower()
        failure_prefixes = (
            "error:", 
            "exception:", 
            "failed to",
            "traceback"
        )
        if text_lower.startswith(failure_prefixes):
            return False
            
        return True