import json
import uuid
import asyncio
from typing import List, Dict, LiteralString, Optional, Any, cast
from loguru import logger
from pydantic import BaseModel, Field

from app.schemas.graph.knowledge_graph_schema import GraphComponents
from app.services.llm.llm_service import LLMService
from app.configs.storage.databases import genome_connection_pool, neo4j_driver
from langchain_qdrant import QdrantVectorStore

class GraphIngestionService:
    def __init__(self, llm_service: LLMService, vector_store: QdrantVectorStore):
        self.llm_service = llm_service
        self.vector_store = vector_store
        self.allowed_labels = {"Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"}

    async def extract_components(self, text: str) -> GraphComponents:
        prompt = f"""
            You are a precise biological knowledge graph relationship extractor.
            Extract all relationships from the text.
            
            CRITICAL RULES:
            1. Node labels MUST be one of these exact types: Gene, Cultivar, Paper, Trait, Disease, Tissue, Stress.
            2. Relationship types MUST be uppercase strings (e.g., UPREGULATES, CAUSES, RESISTS, MENTIONS).
            3. Extract all explicit and implicit biological relationships.
            
            Text to analyze:
            {text}
        """
        model = self.llm_service.get_secondary_model().with_structured_output(GraphComponents)
        result = await model.ainvoke(prompt)
        return cast(GraphComponents, result)

    async def ingest_knowledge(self, source_text: str, source_metadata: Optional[Dict[str, Any]] = None):
        try:
            components = await self.extract_components(source_text)
            node_registry = {}
            source_meta = source_metadata or {}
            
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
                        "recent_source": source_meta
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
            
            logger.info("Saving to Neo4j...")
            async with neo4j_driver.session() as session:
                for node in components.nodes:
                    if node.name in node_registry:
                        node_info = node_registry[node.name]
                        # MERGE handles the duplicate check. We only set the UUID if it's newly created.
                        query = f"""
                        MERGE (n:{node_info['label']} {{name: $name}})
                        ON CREATE SET n.id = $id, n.description = $desc
                        ON MATCH SET n.description = coalesce($desc, n.description)
                        """
                        await session.run(cast(LiteralString, query), name=node.name, id=str(node_info['id']), desc=node.description)
                
                for rel in components.relationships:
                    if rel.source_name in node_registry and rel.target_name in node_registry:
                        source = node_registry[rel.source_name]
                        target = node_registry[rel.target_name]
                        
                        # SANITIZE relationship type to prevent Cypher syntax crashes
                        safe_rel_type = rel.type.strip().upper().replace(" ", "_").replace("-", "_")
                        
                        query = f"""
                        MATCH (a:{source['label']} {{name: $source_name}}), (b:{target['label']} {{name: $target_name}})
                        MERGE (a)-[r:{safe_rel_type}]->(b)
                        """
                        await session.run(cast(LiteralString, query), source_name=rel.source_name, target_name=rel.target_name)
            
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
                        "name": node.name
                    })
                    ids.append(str(node_info['id'])) # Qdrant accepts string UUIDs natively
                    
            if documents:
                await self.vector_store.aadd_texts(texts=documents, metadatas=metadatas, ids=ids)
                
            logger.info(f"Graph ingestion complete: {len(components.nodes)} nodes, {len(components.relationships)} relationships.")
            
        except Exception as e:
            logger.error(f"Graph ingestion failed: {str(e)}")