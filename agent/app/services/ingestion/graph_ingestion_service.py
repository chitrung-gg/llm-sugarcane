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
from app.common.constants import SYSTEM_OWNER_ID


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
        project_name: Optional[str] = None,
        owner_id: uuid.UUID = SYSTEM_OWNER_ID,
        is_public: Optional[bool] = None
    ):
        try:
            source_meta = source_metadata or {}
            tool_name = source_meta.get("tool", "unknown")

            # 1. Fetch Tool Configuration
            tool_config = KNOWLEDGE_GRAPH_TOOL_REGISTRY.get(tool_name)
            if not tool_config:
                logger.info(f"Source '{tool_name}' not in registry. Defaulting to general text ingestion.")

                is_system = (owner_id == SYSTEM_OWNER_ID)

                tool_config = IngestionConfig(
                    # If it's a user file, send to VOLATILE. If system, send to SOLID.
                    vector_store_type=VectorStoreType.SOLID if is_system else VectorStoreType.VOLATILE, 
                    source_type_label=IngestionSourceType.SYSTEM_CURATED_DOCUMENT if is_system else IngestionSourceType.USER_PRIVATE_DOCUMENT,
                    ingestion_confidence_tier=IngestionConfidenceTier.INFERRED, 
                    skip_relevance_check=False,
                    is_public=is_system # Public if system, private if user
                )
            
            # Use provided is_public or default to tool_config
            final_is_public = is_public if is_public is not None else tool_config.is_public

            # Fast-fail: Do not ingest tool error messages or "not found" results.
            if not self._is_ingestable_payload(source_text):
                logger.debug(f"Graph Ingestion Aborted: Output from {tool_name} failed heuristic checks.")
                return
            
            # 2. Extract Data via LLM
            components = await self.extract_components(source_text)

            # 3. Validation & The "Confidence Circuit Breaker"
            if not tool_config.skip_relevance_check and not components.is_domain_relevant:
                logger.warning(f"Ingestion Aborted: Output from {tool_name} is not domain relevant.")
                return
            
            # 3.1. USE LLM CONFIDENCE
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

            unique_nodes = {node.name: node for node in components.nodes if node.label in self.allowed_labels}.values()
            node_registry = {}

            # 5. Save to PostgreSQL
            logger.info(f"Saving to PostgreSQL (Owner: {owner_id}, Public: {final_is_public})...")
            async with genome_connection_pool.connection() as conn:
                for node in unique_nodes:
                    if node.label not in self.allowed_labels:
                        continue
                        
                    global_id = uuid.uuid4()
                    node_registry[node.name] = {"id": global_id, "label": node.label}
                    
                    # Construct metadata JSON
                    meta_payload = json.dumps({
                        "description": node.description,
                        "aliases": node.aliases,
                        "recent_source": source_meta,
                        "llm_overall_confidence": components.overall_confidence
                    })
                    
                    # Upsert Postgres with composite unique constraint (name, owner_id)
                    await conn.execute(
                        """
                        INSERT INTO knowledge_entities (global_id, name, entity_type, owner_id, is_public, knowledge_entities_metadata)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (name, owner_id) DO UPDATE 
                        SET entity_type = EXCLUDED.entity_type,
                            is_public = EXCLUDED.is_public,
                            knowledge_entities_metadata = COALESCE(knowledge_entities.knowledge_entities_metadata, '{}'::jsonb) || EXCLUDED.knowledge_entities_metadata
                        RETURNING global_id
                        """,
                        (global_id, node.name, node.label, owner_id, final_is_public, meta_payload)
                    )

            # 6. Save to Neo4j
            logger.info("Saving to Neo4j safely via LangChain...")
            langchain_nodes = {}
            for node in unique_nodes:
                if node.name in node_registry:
                    node_info = node_registry[node.name]
                    
                    lc_node = Node(
                        id=f"{node.name}_{owner_id}", # Scoped ID for Neo4j
                        type=node_info['label'], 
                        properties={
                            "name": node.name,
                            "global_id": str(node_info['id']),
                            "owner_id": str(owner_id),
                            "is_public": final_is_public,
                            "description": node.description
                        }
                    )
                    langchain_nodes[node.name] = lc_node

            langchain_rels = []
            for rel in components.relationships:
                if rel.confidence < 0.4:
                    continue

                if rel.source_name in langchain_nodes and rel.target_name in langchain_nodes:
                    source_node = langchain_nodes[rel.source_name]
                    target_node = langchain_nodes[rel.target_name]
                    
                    safe_type = rel.type.strip().upper().replace(" ", "_").replace("-", "_")
                    
                    lc_rel = Relationship(
                        source=source_node,
                        target=target_node,
                        type=safe_type,
                        properties={
                            "evidence": rel.evidence,
                            "context": rel.context,
                            "confidence": rel.confidence,
                            "owner_id": str(owner_id),
                            "is_public": final_is_public,
                            "source_type": tool_config.source_type_label, 
                            "source_tier": tool_config.ingestion_confidence_tier.value,
                            "tool_used": tool_name
                        }
                    )
                    langchain_rels.append(lc_rel)

            if langchain_rels:
                graph_document = GraphDocument(
                    nodes=list(langchain_nodes.values()),
                    relationships=langchain_rels,
                    source=Document(page_content=source_text)
                )

                await asyncio.to_thread(
                    self.knowledge_graph.add_graph_documents,
                    [graph_document],
                    baseEntityLabel=True
                )
            
            # 7. Save to Qdrant
            logger.info("Saving to Qdrant concurrently...")
            
            # Helper function to embed a single node
            async def _embed_single_node(node_name, text, meta, n_id):
                try:
                    await asyncio.to_thread(
                        target_vector_store.add_texts,
                        texts=[text], 
                        metadatas=[meta], 
                        ids=[n_id]
                    )
                    return True  # Success
                except Exception as e:
                    logger.warning(f"⚠️ Dropped node '{node_name}' due to embedding failure (Likely Google Safety Filter): {e}")
                    return False # Failure

            tasks = []
            
            # 1. Build the tasks
            for node in unique_nodes: # Or components.nodes based on your actual variable
                if node.name in node_registry:
                    node_info = node_registry[node.name]
                    text_to_embed = f"{node.name} is a {node_info['label']}. Owner: {owner_id}. Description: {node.description or 'None'}. Context: {source_text[:200]}..."
                    
                    metadata = {
                        "global_id": str(node_info['id']),
                        "entity_type": node_info['label'], 
                        "name": node.name,
                        "owner_id": str(owner_id),
                        "is_public": final_is_public,
                        "project_name": project_name,
                        "source_tier": tool_config.ingestion_confidence_tier.value,
                        "tool_used": tool_name,
                        "llm_confidence": components.overall_confidence
                    }
                    node_id = str(node_info['id'])
                    
                    # Add the un-awaited task to our list
                    tasks.append(_embed_single_node(node.name, text_to_embed, metadata, node_id))
            
            # 2. Execute all tasks in parallel!
            if tasks:
                # return_exceptions=True prevents one bad task from cancelling the others
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r is True)
            else:
                success_count = 0
                
            logger.info(f"Graph ingestion complete: {success_count}/{len(tasks)} nodes successfully embedded for owner {owner_id}.")  
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
