import json
import uuid
import asyncio
from typing import List, Dict, LiteralString, Optional, Any, cast
from langchain_neo4j import Neo4jGraph
from loguru import logger
from pydantic import BaseModel, Field

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
        vector_store: QdrantVectorStore
    ):
        self.llm_service = llm_service
        self.knowledge_graph = knowledge_graph
        self.vector_store = vector_store
        self.allowed_labels = {"Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"}

    async def extract_components(self, text: str) -> KnowledgeGraphComponents:
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
        model = self.llm_service.get_secondary_model().with_structured_output(KnowledgeGraphComponents)
        result = await model.ainvoke(prompt)
        return cast(KnowledgeGraphComponents, result)

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
            
            logger.info("Saving to Neo4j safely via LangChain...")

            # 1. Convert your custom Pydantic Nodes into LangChain Nodes
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

            # 2. Convert your custom Pydantic Relationships into LangChain Relationships
            langchain_rels = []
            for rel in components.relationships:
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
                            "context": rel.context
                        }
                    )
                    langchain_rels.append(lc_rel)

            # 3. Create a GraphDocument and let LangChain handle the complex MERGE logic!
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