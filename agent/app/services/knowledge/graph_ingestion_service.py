import uuid
import asyncio
from typing import List, Dict, LiteralString, Optional, Any, cast
from loguru import logger
from pydantic import BaseModel, Field

from app.services.llm.llm_service import LLMService
from app.configs.storage.databases import langgraph_connection_pool, neo4j_driver
from langchain_qdrant import QdrantVectorStore


class GraphNode(BaseModel):
    name: str = Field(description="The name of the entity.")
    label: str = Field(description="Strictly one of: 'Gene', 'Cultivar', 'Paper', 'Trait', 'Disease', 'Tissue', 'Stress'")


class GraphRelationship(BaseModel):
    source_name: str
    target_name: str
    type: str = Field(description="The type of relationship (e.g., 'AFFECTS', 'EXPRESSES', 'STUDIES'). Must be uppercase.")


class GraphComponents(BaseModel):
    nodes: List[GraphNode] = Field(description="List of entities extracted from the text.")
    relationships: List[GraphRelationship] = Field(description="List of relationships between entities.")


class GraphIngestionService:
    def __init__(self, llm_service: LLMService, vector_store: QdrantVectorStore):
        self.llm_service = llm_service
        self.vector_store = vector_store
        
        self.allowed_labels = {"Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"}

    async def extract_components(self, text: str) -> GraphComponents:
        """Extracts nodes and relationships from text using Gemini Flash."""
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
        
        model = self.llm_service.get_quaternary_model().with_structured_output(GraphComponents)
        logger.info("Extracting graph components using LLM...")
        result = await model.ainvoke(prompt)
        
        # Use cast to satisfy the strict type checker
        return cast(GraphComponents, result)

    # Fixed the type hint here by adding Optional and Any
    async def ingest_knowledge(self, source_text: str, source_metadata: Optional[Dict[str, Any]] = None):
        """
        Main pipeline: Extract -> Write Postgres -> Write Neo4j -> Write Qdrant.
        Runs asynchronously to prevent blocking the LangGraph node.
        """
        try:
            # 1. Extraction
            components = await self.extract_components(source_text)
            
            # Map names to their new or existing UUIDs
            node_registry = {}
            
            # 2. Postgres Metadata (System of Record)
            logger.info("Saving to PostgreSQL...")
            async with langgraph_connection_pool.connection() as conn:
                for node in components.nodes:
                    if node.label not in self.allowed_labels:
                        logger.warning(f"Skipping node {node.name} with invalid label {node.label}")
                        continue
                        
                    global_id = uuid.uuid4()
                    node_registry[node.name] = {"id": global_id, "label": node.label}
                    
                    # Upsert KnowledgeEntity (Fixed the string quotes here)
                    await conn.execute(
                        """
                        INSERT INTO knowledge_entities (global_id, name, entity_type, knowledge_entities_metadata)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (name) DO UPDATE 
                        SET entity_type = EXCLUDED.entity_type,
                            knowledge_entities_metadata = EXCLUDED.knowledge_entities_metadata
                        RETURNING global_id
                        """,
                        (global_id, node.name, node.label, None)
                    )
            
            # 3. Neo4j Graph
            logger.info("Saving to Neo4j...")
            async with neo4j_driver.session() as session:
                for node in components.nodes:
                    if node.name in node_registry:
                        node_info = node_registry[node.name]
                        # Fixed the string quotes here
                        query = f"""
                        MERGE (n:{node_info['label']} {{name: $name}})
                        ON CREATE SET n.id = $id
                        ON MATCH SET n.id = $id
                        """
                        await session.run(cast(LiteralString, query), name=node.name, id=str(node_info['id']))
                
                for rel in components.relationships:
                    if rel.source_name in node_registry and rel.target_name in node_registry:
                        source = node_registry[rel.source_name]
                        target = node_registry[rel.target_name]
                        
                        # Fixed the string quotes here
                        query = f"""
                        MATCH (a:{source['label']} {{name: $source_name}}), (b:{target['label']} {{name: $target_name}})
                        MERGE (a)-[r:{rel.type}]->(b)
                        """
                        await session.run(cast(LiteralString, query), source_name=rel.source_name, target_name=rel.target_name)
            
            # 4. Qdrant Embeddings
            logger.info("Saving to Qdrant...")
            documents = []
            metadatas = []
            ids = []
            
            for node in components.nodes:
                if node.name in node_registry:
                    node_info = node_registry[node.name]
                    text_to_embed = f"{node.name} is a {node_info['label']}. Context: {source_text[:200]}..."
                    documents.append(text_to_embed)
                    metadatas.append({"global_id": str(node_info['id']), "entity_type": node_info['label'], "name": node.name})
                    ids.append(str(node_info['id']))
                    
            if documents:
                await self.vector_store.aadd_texts(
                    texts=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                
            logger.info(f"Graph ingestion complete: {len(components.nodes)} nodes, {len(components.relationships)} relationships.")
            
        except Exception as e:
            logger.error(f"Graph ingestion failed: {str(e)}")