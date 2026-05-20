from http import HTTPStatus
import json
import random
import uuid
import asyncio
import hashlib
from typing import List, Dict, Optional, Any, cast

from langchain_neo4j import Neo4jGraph
from loguru import logger

from app.utils.graph.context_utils import generate_entity_uuid
from app.configs.settings.settings import get_settings
from app.core.prompts.graph_ingestion_prompts import EXTRACTION_PROMPT
from app.core.tools.registry.ingestion_config_tool import IngestionConfig
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionConfidenceTier, IngestionSourceType
from app.core.tools.registry.registry_tool import KNOWLEDGE_GRAPH_TOOL_REGISTRY
from app.core.vector_store.vector_store import VectorStoreType
from app.schemas.graph.knowledge_graph_schema import KnowledgeGraphComponents
from app.services.llm.llm_service import LLMService
from app.configs.storage.databases import genome_connection_pool, userdata_connection_pool
from langchain_qdrant import QdrantVectorStore
from langchain_neo4j.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document
from app.common.constants import SYSTEM_OWNER_ID, GraphIngestionAllowedLabels


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
        self.allowed_labels = set(GraphIngestionAllowedLabels)

    async def ingest_knowledge(
        self,
        source_texts: List[str], 
        source_metadata: Optional[Dict[str, Any]] = None,
        owner_id: uuid.UUID = SYSTEM_OWNER_ID
    ):
        source_meta = source_metadata or {}
        tool_name = source_meta.get("tool", "unknown")
        
        try:
            # 1. Fetch Tool Configuration
            tool_config = KNOWLEDGE_GRAPH_TOOL_REGISTRY.get(tool_name)
            if not tool_config:
                logger.info(f"Source '{tool_name}' not in registry. Defaulting to general text ingestion.")
                is_system = (owner_id == SYSTEM_OWNER_ID)
                tool_config = IngestionConfig(
                    vector_store_type=VectorStoreType.SOLID if is_system else VectorStoreType.VOLATILE, 
                    source_type_label=IngestionSourceType.SYSTEM_CURATED_DOCUMENT if is_system else IngestionSourceType.USER_PRIVATE_DOCUMENT,
                    ingestion_confidence_tier=IngestionConfidenceTier.INFERRED, 
                    skip_relevance_check=True
                )

            # 2. Fast-fail & Deduplicate
            seen_hashes = set()
            unique_ingestable_texts = []
            for t in source_texts:
                if await self._is_ingestable_payload(t):
                    h = await self._get_text_hash(t, source_meta.get("source", ""))
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        unique_ingestable_texts.append(t)
            
            if not unique_ingestable_texts:
                logger.debug(f"Graph Ingestion Batch Aborted: No unique ingestable payloads from {tool_name}.")
                return

            # 3. Extract in batch
            results = await self._extract_components_batch(unique_ingestable_texts)

            if len(results) != len(unique_ingestable_texts):
                logger.error(f"LLM Batch Mismatch: Expected {len(unique_ingestable_texts)} results, got {len(results)}.")
                raise ValueError("Aborting batch ingestion to prevent data corruption.")

            # 4. Validation & Filtering
            valid_chunks = []
            for res, text in zip(results, unique_ingestable_texts):
                if not tool_config.skip_relevance_check and not res.is_domain_relevant:
                    logger.warning(f"The text '{text[:150]}' is being dropped from ingesting due to irrelevant domain")
                    continue

                valid_chunks.append({
                    "components": res,
                    "text": text
                })

            if not valid_chunks:
                logger.debug("Ingestion Aborted: No domain-relevant chunks survived extraction.")
                return

            # 5. Persist
            await self._persist_knowledge_batch(
                valid_chunks=valid_chunks,
                tool_config=tool_config,
                source_meta=source_meta,
                owner_id=owner_id
            )
        except Exception as e:
            logger.error(f"Graph ingestion batch failed: {e}")
            raise e

    async def _persist_knowledge_batch(
        self,
        valid_chunks: List[Dict[str, Any]],
        tool_config: IngestionConfig,
        source_meta: Dict[str, Any],
        owner_id: uuid.UUID
    ):
        file_id_str = source_meta.get("file_id")
        dataset_id_str = source_meta.get("dataset_id")

        # 1. Route to the Correct Vector Store
        target_vector_store = None
        if tool_config.vector_store_type == VectorStoreType.SOLID:
            target_vector_store = self.vector_store_solid
        elif tool_config.vector_store_type == VectorStoreType.VOLATILE:
            target_vector_store = self.vector_store_volatile
        
        if not target_vector_store:
            raise ValueError(f"The vector store type '{tool_config.vector_store_type}' has not been configured.")
        
        # Neo4j Graph Insertion
        graph_documents = []
        global_rel_registry = set()
        
        for chunk in valid_chunks:
            res = chunk["components"]
            if not res.nodes: continue 
            
            local_node_map = {} 
            for node in res.nodes:
                # Merge nodes across files by using OwnerID, not FileID!
                node_uuid = generate_entity_uuid(node.label, node.name)
                
                lc_node = Node(
                    id=node_uuid,
                    type=node.label,
                    properties={
                        "id": node_uuid,
                        "name": node.name,
                        "description": node.description
                    }
                )
                local_node_map[node.name] = lc_node 

            langchain_rels = []
            for rel in res.relationships:
                safe_type = rel.type    # Already validated by Pydantic
                rel_key = (rel.source_name, safe_type, rel.target_name)
                
                if rel_key in global_rel_registry: continue

                s_node = local_node_map.get(rel.source_name)
                t_node = local_node_map.get(rel.target_name)
                
                if s_node and t_node:
                    global_rel_registry.add(rel_key)
                    langchain_rels.append(Relationship(
                        source=s_node, target=t_node, type=safe_type,
                        properties={
                            "confidence": rel.confidence,
                            "source_file_id": file_id_str
                        }
                    ))
            
            if local_node_map:
                graph_documents.append(GraphDocument(
                    nodes=list(local_node_map.values()),
                    relationships=langchain_rels,
                    source=Document(page_content=chunk["text"])
                ))

        if graph_documents:
            logger.info(f"Saving {len(graph_documents)} graph components to Neo4j...")
            await asyncio.to_thread(self.knowledge_graph.add_graph_documents, graph_documents, baseEntityLabel=True)

        # Qdrant Vector Search Ingestion
        documents_to_embed = []
        document_ids = []
        
        for chunk in valid_chunks:
            res = chunk["components"]
            raw_text = chunk["text"]

            # The Bridge: ["Gene::ScDREB2", "Disease::Smut"]
            entity_ids = list(set([
                generate_entity_uuid(n.label, n.name) for n in res.nodes
            ])) if res.nodes else []

            clean_metadata = {
                "file_id": file_id_str,
                "dataset_id": dataset_id_str,
                "owner_id": str(owner_id),
                "source": source_meta.get("source", "unknown_file"),
                "page": source_meta.get("page", 1),
                "entity_ids": entity_ids, 
                "entities": [f"{n.label}::{n.name}" for n in res.nodes]
            }
            
            clean_metadata = {k: v for k, v in clean_metadata.items() if v is not None}
            
            documents_to_embed.append(Document(page_content=raw_text, metadata=clean_metadata))
            document_ids.append(str(uuid.uuid4()))

        # Batch insert to Qdrant
        if documents_to_embed:
            logger.info(f"Packing {len(documents_to_embed)} pure text chunks into Qdrant...")
            batch_size = self.settings.QDRANT_BATCH_SIZE
            for i in range(0, len(documents_to_embed), batch_size):
                batch_docs = documents_to_embed[i : i + batch_size]
                batch_ids = document_ids[i : i + batch_size]
                try:
                    await target_vector_store.aadd_documents(documents=batch_docs, ids=batch_ids)
                except Exception as e:
                    logger.warning("🚨 Sparse/Dense mismatch detected for batch. Isolating chunks sequentially...")
                    # Fallback: Insert 1-by-1 to isolate and identify the exact chunk causing FastEmbed to choke
                    for single_doc, single_id in zip(batch_docs, batch_ids):
                        try:
                            await target_vector_store.aadd_documents(documents=[single_doc], ids=[single_id])
                        except Exception as inner_e:
                            logger.error(f"❌ Skipping toxic chunk that broke FastEmbed: {single_doc.page_content[:100]}... Error: {inner_e}")
                        

    async def _is_ingestable_payload(self, text: str) -> bool:
        clean_text = text.strip()
        if len(clean_text) < 30:
            return False
        if clean_text.lower().startswith(("error:", "exception:", "failed to", "traceback")):
            return False
        return True

    async def _extract_components(self, text: str, max_retries: int = 5) -> KnowledgeGraphComponents:
        prompt = EXTRACTION_PROMPT.format(text=text)
        model = self.llm_service.get_structured_quaternary_model(KnowledgeGraphComponents)
        
        for attempt in range(max_retries):
            try:
                result = await model.ainvoke(prompt)
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[Extraction] Fatal failure after {max_retries} attempts: {e}")
                    raise e
                
                # 1. Safely attempt to extract the exact HTTP status code
                status_code = getattr(e, "status_code", getattr(e, "code", None))
                error_str = str(e).lower()
                
                # 2. Define logic using HTTPStatus (Fixed indentation!)
                is_rate_limit = (
                    status_code == HTTPStatus.TOO_MANY_REQUESTS or 
                    any(key in error_str for key in ["429", "quota", "rate limit"])
                )
                
                is_server_error = (
                    status_code in {
                        HTTPStatus.INTERNAL_SERVER_ERROR, 
                        HTTPStatus.BAD_GATEWAY, 
                        HTTPStatus.SERVICE_UNAVAILABLE, 
                        HTTPStatus.GATEWAY_TIMEOUT
                    } or ("50" in error_str and "internal" in error_str)
                )

                # 3. Determine Delay
                if is_rate_limit:
                    delay = 40.0 + random.uniform(1.0, 5.0)
                    logger.warning(f"[Extraction] 🚨 Rate Limit. Sleeping {delay:.1f}s (Attempt {attempt + 1})")
                    
                elif is_server_error:
                    delay = (2 ** attempt) + random.uniform(0.5, 2.0)
                    logger.warning(f"[Extraction] ⚠️ Server Error. Retrying in {delay:.1f}s...")
                    
                else:
                    delay = 5.0
                    logger.warning(f"[Extraction] ❓ Unexpected Error ({status_code}). Retrying in {delay:.1f}s")
                
                await asyncio.sleep(delay)
                
        # 4. Catch-all to satisfy strict type checkers if max_retries <= 0
        raise ValueError(f"Extraction failed: max_retries was set to {max_retries}")

    async def _extract_components_batch(self, texts: List[str]) -> List[KnowledgeGraphComponents]:
        logger.debug(f"Starting concurrent extraction for {len(texts)} chunks...")
        
        # Concurrency safety limit
        semaphore = asyncio.Semaphore(10)

        async def _bounded_extract(text: str) -> KnowledgeGraphComponents:
            async with semaphore:
                return await self._extract_components(text)

        tasks = [_bounded_extract(text) for text in texts]
        
        start_time = asyncio.get_running_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = asyncio.get_running_loop().time() - start_time
        logger.debug(f"Concurrent extraction for {len(texts)} chunks completed in {duration:.2f}s")
        
        valid_results = []
        all_failed = True
        
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.warning(f"Chunk {i} extraction failed: {str(res)}")
                valid_results.append(KnowledgeGraphComponents(
                    nodes=[], relationships=[], is_domain_relevant=False, overall_confidence=0.0
                ))
            else:
                all_failed = False
                valid_results.append(res)
        
        if all_failed and texts:
            raise ValueError(f"All {len(texts)} chunks in the batch failed extraction. Check API rate limits.")
                
        return valid_results

    async def _get_text_hash(self, text: str, source: str = "") -> str:
        # Prepend source to text to prevent collisions on common short headings
        hash_input = f"{source}::{text}"
        return hashlib.md5(hash_input.encode()).hexdigest()