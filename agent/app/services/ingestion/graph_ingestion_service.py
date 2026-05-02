import json
import uuid
import asyncio
import hashlib
from typing import List, Dict, LiteralString, Optional, Any, cast, Tuple
from langchain_neo4j import Neo4jGraph
from loguru import logger
from pydantic import BaseModel, Field
from langchain.embeddings.base import Embeddings

from app.configs.settings.settings import get_settings
from app.core.prompts.graph_ingestion_prompts import EXTRACTION_PROMPT, BATCH_EXTRACTION_PROMPT
from app.core.tools.registry.ingestion_config_tool import IngestionConfig
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionConfidenceTier, IngestionSourceType
from app.core.tools.registry.registry_tool import KNOWLEDGE_GRAPH_TOOL_REGISTRY
from app.core.vector_store.vector_store import VectorStoreType
from app.schemas.graph.knowledge_graph_schema import KnowledgeGraphComponents, BatchKnowledgeGraphComponents
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
        self.settings = get_settings()
        self.allowed_labels = {"Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"}

    async def extract_components(self, text: str) -> KnowledgeGraphComponents:
        prompt = EXTRACTION_PROMPT.format(text=text)
        model = self.llm_service.get_structured_secondary_model(KnowledgeGraphComponents)
        result = await model.ainvoke(prompt)
        return cast(KnowledgeGraphComponents, result)

    async def extract_components_batch(self, texts: List[str]) -> List[KnowledgeGraphComponents]:
        """
        Extracts components from a list of texts efficiently by using a single batch LLM call.
        Falls back to concurrent individual calls if the batch call fails.
        """
        logger.debug(f"Starting batch extraction for {len(texts)} chunks...")
        for i, text in enumerate(texts):
            logger.debug(f"Chunk {i} [chars={len(text)}]: {text[:150]}...")
        
        try:
            # Try single-call batch extraction first (more efficient)
            # We use json.dumps to ensure the list of strings is formatted correctly for the prompt
            prompt = BATCH_EXTRACTION_PROMPT.format(chunks=json.dumps(texts))
            model = self.llm_service.get_structured_secondary_model(BatchKnowledgeGraphComponents)
            
            start_time = asyncio.get_event_loop().time()
            result = await model.ainvoke(prompt)
            duration = asyncio.get_event_loop().time() - start_time
            logger.debug(f"Batch LLM extraction for {len(texts)} chunks completed in {duration:.2f}s")
            
            # Ensure we got the right number of results
            if len(result.results) == len(texts):
                return result.results
            
            logger.warning(f"Batch extraction returned {len(result.results)} instead of {len(texts)}. Falling back...")
        except Exception as e:
            logger.warning(f"Batch extraction failed: {str(e)}. Falling back to concurrent extraction...")

        # Fallback: Concurrent individual extraction (old behavior)
        tasks = [self.extract_components(text) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        all_failed = True
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.warning(f"Chunk {i} extraction failed: {str(res)}")
                # Append an empty component so the lists remain the same length
                valid_results.append(KnowledgeGraphComponents(
                    nodes=[], relationships=[], is_domain_relevant=False, overall_confidence=0.0
                ))
            else:
                all_failed = False
                valid_results.append(res)
        
        if all_failed and texts:
            raise ValueError(f"All {len(texts)} chunks in batch failed extraction.")
                
        return valid_results

    def _get_text_hash(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    async def ingest_knowledge(
        self,
        source_text: str, 
        source_metadata: Optional[Dict[str, Any]] = None,
        project_name: Optional[str] = None,
        owner_id: uuid.UUID = SYSTEM_OWNER_ID,
        is_public: Optional[bool] = None
    ):
        await self.ingest_knowledge_batch(
            source_texts=[source_text],
            source_metadata=source_metadata,
            project_name=project_name,
            owner_id=owner_id,
            is_public=is_public
        )

    async def ingest_knowledge_batch(
        self,
        source_texts: List[str], 
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
                    vector_store_type=VectorStoreType.SOLID if is_system else VectorStoreType.VOLATILE, 
                    source_type_label=IngestionSourceType.SYSTEM_CURATED_DOCUMENT if is_system else IngestionSourceType.USER_PRIVATE_DOCUMENT,
                    ingestion_confidence_tier=IngestionConfidenceTier.INFERRED, 
                    skip_relevance_check=False,
                    is_public=is_system 
                )
            
            final_is_public = is_public if is_public is not None else tool_config.is_public

            # 2. Fast-fail & Deduplicate
            seen_hashes = set()
            unique_ingestable_texts = []
            for t in source_texts:
                if self._is_ingestable_payload(t):
                    h = self._get_text_hash(t)
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        unique_ingestable_texts.append(t)
            
            if not unique_ingestable_texts:
                logger.debug(f"Graph Ingestion Batch Aborted: No unique ingestable payloads from {tool_name}.")
                return

            # 3. Extract in batch
            results = await self.extract_components_batch(unique_ingestable_texts)

            if len(results) != len(unique_ingestable_texts):
                logger.error(f"LLM Batch Mismatch: Expected {len(unique_ingestable_texts)} results, got {len(results)}. Using zip() which may truncate.")

            # 4. Validation & Filtering
            valid_items = []
            for res, text in zip(results, unique_ingestable_texts):
                if not tool_config.skip_relevance_check and not res.is_domain_relevant:
                    continue
                if not res.nodes:
                    continue
                valid_items.append((res, text))

            if not valid_items:
                logger.debug(f"Graph Ingestion Batch Aborted: No valid components extracted from {tool_name}.")
                return

            # 5. Persist
            await self._persist_knowledge_batch(
                results=[item[0] for item in valid_items],
                source_texts=[item[1] for item in valid_items],
                tool_config=tool_config,
                source_meta=source_meta,
                owner_id=owner_id,
                final_is_public=final_is_public,
                project_name=project_name
            )
        except Exception as e:
            logger.error(f"Graph ingestion batch failed: {e}")
            raise e

    async def _persist_knowledge_batch(
        self,
        results: List[KnowledgeGraphComponents],
        source_texts: List[str],
        tool_config: IngestionConfig,
        source_meta: Dict[str, Any],
        owner_id: uuid.UUID,
        final_is_public: bool,
        project_name: Optional[str] = None
    ):
        tool_name = source_meta.get("tool", "unknown")

        # 1. Route to the Correct Vector Store
        target_vector_store = None
        if tool_config.vector_store_type == VectorStoreType.SOLID:
            target_vector_store = self.vector_store_solid
        elif tool_config.vector_store_type == VectorStoreType.VOLATILE:
            target_vector_store = self.vector_store_volatile
        else:
            logger.error("The vector store type has not been configured.")
            return

        # 2. Entity Deduplication (Keep HIGHEST overall_confidence)
        # We also store the associated chunk text for Qdrant summaries.
        unique_nodes_registry = {} # name -> (node_obj, confidence, chunk_text)
        
        for res, text in zip(results, source_texts):
            for node in res.nodes:
                if node.label not in self.allowed_labels:
                    continue
                
                if node.name not in unique_nodes_registry or res.overall_confidence > unique_nodes_registry[node.name][1]:
                    unique_nodes_registry[node.name] = (node, res.overall_confidence, text)

        node_registry = {} # name -> {"id": uuid, "label": str}

        # 3. Save to PostgreSQL (Upsert Unique Entities)
        logger.info(f"Saving {len(unique_nodes_registry)} unique entities to PostgreSQL...")
        async with genome_connection_pool.connection() as conn:
            for node_name, (node, confidence, _) in unique_nodes_registry.items():
                temp_id = uuid.uuid4()
                
                meta_payload = json.dumps({
                    "description": node.description,
                    "aliases": node.aliases,
                    "recent_source": source_meta,
                    "llm_overall_confidence": confidence
                })
                
                res_pg = await conn.execute(
                    """
                    INSERT INTO knowledge_entities (global_id, name, entity_type, owner_id, is_public, knowledge_entities_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (name, owner_id) DO UPDATE 
                    SET entity_type = EXCLUDED.entity_type,
                        is_public = EXCLUDED.is_public,
                        knowledge_entities_metadata = COALESCE(knowledge_entities.knowledge_entities_metadata, '{}'::jsonb) || EXCLUDED.knowledge_entities_metadata
                    RETURNING global_id
                    """,
                    (temp_id, node.name, node.label, owner_id, final_is_public, meta_payload)
                )
                row = await res_pg.fetchone()
                if row:
                    node_registry[node.name] = {"id": row["global_id"], "label": node.label}

        # 4. Save to Neo4j (Add all GraphDocuments in one call)
        logger.info(f"Saving {len(results)} chunks to Neo4j...")
        graph_documents = []
        for res, text in zip(results, source_texts):
            langchain_nodes = {}
            for node in res.nodes:
                if node.name in node_registry:
                    node_info = node_registry[node.name]
                    lc_node = Node(
                        id=f"{node.name}_{owner_id}",
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
            for rel in res.relationships:
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
            
            if langchain_rels or langchain_nodes:
                graph_documents.append(GraphDocument(
                    nodes=list(langchain_nodes.values()),
                    relationships=langchain_rels,
                    source=Document(page_content=text)
                ))

        if graph_documents:
            await asyncio.to_thread(
                self.knowledge_graph.add_graph_documents,
                graph_documents,
                baseEntityLabel=True
            )

        # 5. Save to Qdrant (Loop over UNIQUE entities from deduplicated list)
        logger.info("Saving unique node summaries to Qdrant...")
        documents_to_embed = []
        document_ids = []
        
        seen_texts = set() # For deduplicating identical summaries
        
        for node_name, (node, confidence, text) in unique_nodes_registry.items():
            if node_name in node_registry:
                node_info = node_registry[node_name]
                text_to_embed = (
                    f"ENTITY KNOWLEDGE SUMMARY:\n"
                    f"Name: {node.name}\n"
                    f"Type: {node_info['label']}\n"
                    f"Description: {node.description or 'No explicit description provided.'}\n"
                    f"Original Context: {text[:300]}..."
                )
                
                if not text_to_embed.strip():
                    logger.warning(f"Skipping empty text for node: {node_name}")
                    continue

                # Deduplicate identical summaries to prevent Gemini/FastEmbed batching issues
                if text_to_embed in seen_texts:
                    logger.debug(f"Skipping duplicate summary for node: {node_name}")
                    continue
                seen_texts.add(text_to_embed)

                metadata = {
                    **source_meta, # Spread original metadata to preserve fields like original_filename
                    "global_id": str(node_info['id']),
                    "entity_type": node_info['label'], 
                    "name": node.name,
                    "owner_id": str(owner_id),
                    "is_public": final_is_public,
                    "project_name": project_name,
                    "source_tier": tool_config.ingestion_confidence_tier.value,
                    "tool_used": tool_name,
                    "llm_confidence": confidence,
                    "chunk_type": "entity_summary" 
                }
                doc = Document(page_content=text_to_embed, metadata=metadata)
                documents_to_embed.append(doc)
                document_ids.append(str(node_info['id']))

        if documents_to_embed:
            # Large batches can cause the dense/sparse embedders to return mismatched results or hit timeouts.
            
            total_docs = len(documents_to_embed)
            logger.debug(f"Sending {total_docs} documents to Qdrant in batches of {self.settings.QDRANT_BATCH_SIZE}...")
            
            for i in range(0, total_docs, self.settings.QDRANT_BATCH_SIZE):
                batch_docs = documents_to_embed[i : i + self.settings.QDRANT_BATCH_SIZE]
                batch_ids = document_ids[i : i + self.settings.QDRANT_BATCH_SIZE]
                
                logger.debug(f"Ingesting Qdrant batch {i//self.settings.QDRANT_BATCH_SIZE + 1} ({len(batch_docs)} docs)...")
                try:
                    await target_vector_store.aadd_documents(
                        documents=batch_docs,
                        ids=batch_ids
                    )
                    if i + self.settings.QDRANT_BATCH_SIZE < total_docs:
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    logger.warning(f"Batch {i} length mismatch! Isolating embedders to debug...")
                    texts_to_embed = [doc.page_content for doc in batch_docs]
                    
                    # 1. Manually test the embedders to identify the culprit
                    dense = cast(Embeddings, target_vector_store.embeddings)
                    sparse = cast(Embeddings, target_vector_store.sparse_embeddings)

                    dense_results = await dense.aembed_documents(texts_to_embed)
                    sparse_results = await sparse.aembed_documents(texts_to_embed)

                    dense_len = len(dense_results)
                    sparse_len = len(sparse_results)
                    logger.error(f"Input: {len(texts_to_embed)} | Dense Output: {dense_len} | Sparse Output: {sparse_len}")
                    
                    # 2. Fallback: Process 1-by-1 to save the good docs and catch the bad one
                    logger.info("Falling back to sequential ingestion for this batch...")
                    for single_doc, single_id in zip(batch_docs, batch_ids):
                        try:
                            await target_vector_store.aadd_documents(
                                documents=batch_docs,
                                ids=batch_ids
                            )
                        except Exception as inner_e:
                            logger.error(f"Failed on specific document ID {single_id}: {inner_e}")
                            logger.error(f"Problematic Text: {single_doc.page_content}")
            
            logger.info(f"Qdrant ingestion complete: {total_docs} unique entities embedded.")

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
