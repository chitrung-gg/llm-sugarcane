# import ast
# import asyncio
# import gc
# import os
# import re
# import uuid
# from typing import Any, Dict, Optional, cast, AsyncContextManager

# from celery import Task
# from celery.signals import worker_process_shutdown
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from loguru import logger
# from types_aiobotocore_s3 import S3Client

# from app.configs.settings.settings import get_settings
# from app.core.workers.celery import celery
# from app.core.app_container import get_container
# from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool

# from app.core.tools.registry.registry_tool import KNOWLEDGE_GRAPH_TOOL_REGISTRY
# from app.core.tools.registry.ingestion_config_tool import IngestionConfig
# from app.core.vector_store.vector_store import VectorStoreType
# from app.schemas.knowledge.knowledge_ingestion_schema import IngestionConfidenceTier, IngestionSourceType
# from app.common.constants import SYSTEM_OWNER_ID

# if "manual_document_upload" not in KNOWLEDGE_GRAPH_TOOL_REGISTRY:
#     KNOWLEDGE_GRAPH_TOOL_REGISTRY["manual_document_upload"] = IngestionConfig(
#         vector_store_type=VectorStoreType.SOLID,
#         source_type_label=IngestionSourceType.USER_PRIVATE_DOCUMENT, 
#         ingestion_confidence_tier=IngestionConfidenceTier.CURATED, 
#         skip_relevance_check=False,
#         is_public=False
#     )

# try:
#     import app.core.tools.ncbi_eutils_tool
#     logger.info("Successfully registered NCBI tools into Celery Registry.")
    
# except ImportError as e:
#     logger.warning(f"Could not import NCBI tools for registry: {e}")
    
# class AsyncBioinformaticsTask(Task):
#     """
#     Custom Celery Task base class that maintains a persistent event loop
#     and a single initialized container per worker process.
#     """
#     abstract = True
#     _loop = None
#     _container_ready = False

#     @property
#     def worker_loop(self):
#         """Lazily initializes and returns a persistent event loop for this worker process."""
#         if self._loop is None:
#             self._loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(self._loop)
#         return self._loop

#     async def get_ready_container_async(self):
#         """Asynchronously ensures the AppContainer is initialized exactly once."""
#         container = get_container()
        
#         if not self._container_ready:
#             logger.info("Initializing AppContainer on persistent worker loop...")
            
#             # 🌟 FIX: Manually open the database connection pools for the Celery Worker
#             logger.info("🔌 Opening Genome PostgreSQL connection pool in Celery...")
#             await genome_connection_pool.open()
            
#             logger.info("🔌 Opening LangGraph PostgreSQL connection pool in Celery...")
#             await langgraph_connection_pool.open()

#             # Now that pools are open, initialize the container
#             await container.initialize()
#             self._container_ready = True
            
#         return container

#     def execute_async(self, coro):
#         """Helper method to execute async code on the persistent loop."""
#         return self.worker_loop.run_until_complete(coro)


# @celery.task(name="llm.tasks.ingest_knowledge", bind=True, base=AsyncBioinformaticsTask)
# def celery_ingest_graph_knowledge(self, source_text: str, source_metadata: Optional[Dict[str, Any]] = None):
#     logger.info(f"Celery picked up graph ingestion task. Text length: {len(source_text)}")

#     async def async_runner():
#         # Await the container initialization INSIDE the async block
#         container = await self.get_ready_container_async()
        
#         meta = source_metadata or {}
#         owner_id_str = meta.get("owner_id")
#         owner_id = uuid.UUID(owner_id_str) if owner_id_str and owner_id_str != "SYSTEM" else SYSTEM_OWNER_ID

#         await container.graph_ingestion_service.ingest_knowledge(
#             source_text=source_text,
#             source_metadata=source_metadata,
#             owner_id=owner_id,
#             is_public=meta.get("is_public")
#         )

#     try:
#         # Run everything in ONE continuous loop execution
#         self.execute_async(async_runner())
#     except Exception as exc:
#         logger.error(f"Celery ingestion task failed: {str(exc)}")
#         raise self.retry(exc=exc, countdown=10)


# @celery.task(name="llm.tasks.process_document_ingestion", bind=True, base=AsyncBioinformaticsTask)
# def process_document_ingestion(self, target_uri: str, metadata: dict):
#     settings = get_settings()

#     async def async_run():
#         # Await the container initialization INSIDE the async block
#         container = await self.get_ready_container_async()

#         local_file_path = target_uri
#         is_remote = target_uri.startswith("s3://")
#         s3_bucket, s3_key = "", ""

#         chunks = None
#         raw_chunks = None

#         try:
#             self.update_state(state='PROGRESS', meta={'message': 'Initializing download...'})
            
#             if is_remote:
#                 parts = target_uri.replace("s3://", "").split("/", 1)
#                 s3_bucket, s3_key = parts[0], parts[1]
#                 ext = os.path.splitext(s3_key)[1]
#                 local_file_path = f"/tmp/worker_{uuid.uuid4()}{ext}"
                
#                 rustfs_client = cast(
#                     AsyncContextManager[S3Client],
#                     container.rustfs_session.client(
#                         's3',
#                         endpoint_url=settings.rustfs_endpoint_url,
#                         aws_access_key_id=settings.rustfs_access_key_id,
#                         aws_secret_access_key=settings.rustfs_secret_access_key,
#                         region_name=settings.rustfs_region_name
#                     )
#                 )

#                 async with rustfs_client as s3_client:
#                     await s3_client.download_file(s3_bucket, s3_key, local_file_path)

#             self.update_state(state='PROGRESS', meta={'message': 'Parsing document with Docling...'})
#             chunks = container.document_processor.process_and_get_chunks(local_file_path)
#             total_chunks = len(chunks)
            
#             BATCH_SIZE = 8     # Number of chunks processed at the same time (adjust based on your Gemini API tier)
#             DELAY_BETWEEN_BATCHES = 30 # Delay between batches to avoid rate limiting

#             pending_chunks = [(i, chunk) for i, chunk in enumerate(chunks)]

#             while pending_chunks:
#                 current_batch = pending_chunks[:BATCH_SIZE]
#                 pending_chunks = pending_chunks[BATCH_SIZE:]
                
#                 current_count = total_chunks - len(pending_chunks)
#                 percent = round((current_count / total_chunks) * 100, 2)
                
#                 logger.info(f"[Task {self.request.id}] Ingesting batch: {current_count}/{total_chunks} chunks processed ({percent}%)")
                
#                 self.update_state(
#                     state='PROGRESS', 
#                     meta={
#                         'current': current_count, 
#                         'total': total_chunks,
#                         'percent': percent,
#                         'message': f'Ingesting batch: {current_count}/{total_chunks}'
#                     }
#                 )

#                 tasks = []
#                 owner_id_str = metadata.get("owner_id")
#                 owner_id = uuid.UUID(owner_id_str) if owner_id_str and owner_id_str != "SYSTEM" else SYSTEM_OWNER_ID
#                 is_public = metadata.get("is_public")

#                 for chunk_index, chunk in current_batch:
#                     task = container.graph_ingestion_service.ingest_knowledge(
#                         source_text=chunk.page_content,
#                         source_metadata={
#                             **metadata, 
#                             "tool": "manual_document_upload", 
#                             "chunk_index": chunk_index
#                         },
#                         owner_id=owner_id,
#                         is_public=is_public
#                     )
#                     tasks.append(task)

#                 results = await asyncio.gather(*tasks, return_exceptions=True)

#                 rate_limit_hit = False

#                 for (chunk_index, chunk), result in zip(current_batch, results):
#                     if isinstance(result, Exception):
#                         error_type = type(result).__name__
#                         error_str = str(result)
#                         is_rate_limit = False
                        
#                         status_code = getattr(result, 'code', None) or getattr(result, 'status_code', None)
#                         if status_code == 429 or error_type in ["ResourceExhausted", "RateLimitError"]:
#                             is_rate_limit = True
#                         elif "{" in error_str:
#                             dict_str = error_str[error_str.find("{"):]
#                             try:
#                                 error_data = ast.literal_eval(dict_str)
#                                 err_payload = error_data.get("error", {})
#                                 if err_payload.get("code") == 429 or err_payload.get("status") == "RESOURCE_EXHAUSTED":
#                                     is_rate_limit = True
#                             except (ValueError, SyntaxError):
#                                 if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
#                                     is_rate_limit = True

#                         if is_rate_limit:
#                             pending_chunks.insert(0, (chunk_index, chunk))
#                             rate_limit_hit = True
#                         else:
#                             logger.error(f"[Task {self.request.id}] Failed chunk {chunk_index}: {error_type} - {error_str}")

#                 if rate_limit_hit:
#                     logger.warning("Hit API Rate Limit. Pausing for 60s before retrying failed chunks in place...")
#                     await asyncio.sleep(60)
#                 elif pending_chunks:
#                     await asyncio.sleep(DELAY_BETWEEN_BATCHES)

#             return {
#                 "status": "success", 
#                 "message": "Ingestion complete.",
#                 "chunks_processed": total_chunks
#             }

#         except Exception as e:
#             logger.error(f"[Task {self.request.id}] Fatal Error: {str(e)}")
#             raise e

#         finally:
#             self.update_state(state='CLEANUP', meta={'message': 'Cleaning up temporary files...'})
            
#             if is_remote and os.path.exists(local_file_path):
#                 os.remove(local_file_path)

#             if chunks is not None:
#                 del chunks
#             if raw_chunks is not None:
#                 del raw_chunks
#             gc.collect()

#     # Run everything in ONE continuous loop execution
#     return self.execute_async(async_run())

# from celery.signals import worker_process_shutdown

# @worker_process_shutdown.connect
# def shutdown_worker_process(**kwargs):
#     """Gracefully close database pools when the Celery worker shuts down."""
    
#     # We need to run the async close methods in the synchronous shutdown hook
#     async def close_pools():
#         logger.info("🛑 Shutting down Celery worker process...")
#         try:
#             await genome_connection_pool.close()
#             logger.info("🔌 Closed Genome pool.")
#         except Exception:
#             pass
            
#         try:
#             await langgraph_connection_pool.close()
#             logger.info("🔌 Closed LangGraph pool.")
#         except Exception:
#             pass

#     # Execute the shutdown on the worker's persistent loop if it exists
#     loop = asyncio.get_event_loop()
#     if loop and not loop.is_closed():
#         loop.run_until_complete(close_pools())
