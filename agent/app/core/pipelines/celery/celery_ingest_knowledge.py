import asyncio
import gc
import os
import uuid
from typing import Any, Dict, Optional, cast, AsyncContextManager

from celery import Task
from celery.signals import worker_process_shutdown
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from types_aiobotocore_s3 import S3Client

from app.configs.settings.settings import get_settings
from app.core.workers.celery import celery
from app.core.app_container import get_container
from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool

from app.core.tools.registry.registry_tool import KNOWLEDGE_GRAPH_TOOL_REGISTRY
from app.core.tools.registry.ingestion_config_tool import IngestionConfig
from app.core.vector_store.vector_store import VectorStoreType
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionConfidenceTier, IngestionSourceType

if "manual_document_upload" not in KNOWLEDGE_GRAPH_TOOL_REGISTRY:
    KNOWLEDGE_GRAPH_TOOL_REGISTRY["manual_document_upload"] = IngestionConfig(
        vector_store_type=VectorStoreType.SOLID,
        source_type_label=IngestionSourceType.CURATED_DOCUMENT, # Đảm bảo Enum này khớp với schema của bạn
        ingestion_confidence_tier=IngestionConfidenceTier.CURATED, 
        skip_relevance_check=False
    )

# B. Đăng ký Pipeline 2 (NCBI Tools): Import file chứa các tool để decorator tự chạy
try:
    # LƯU Ý: Hãy thay đổi đường dẫn import này cho đúng với file chứa các NCBI tool của bạn
    import app.core.tools.ncbi_eutils_tool
    logger.info("Successfully registered NCBI tools into Celery Registry.")
    
except ImportError as e:
    logger.warning(f"Could not import NCBI tools for registry: {e}")
    
class AsyncBioinformaticsTask(Task):
    """
    Custom Celery Task base class that maintains a persistent event loop
    and a single initialized container per worker process.
    """
    abstract = True
    _loop = None
    _container_ready = False

    @property
    def worker_loop(self):
        """Lazily initializes and returns a persistent event loop for this worker process."""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    async def get_ready_container_async(self):
        """Asynchronously ensures the AppContainer is initialized exactly once."""
        container = get_container()
        
        if not self._container_ready:
            logger.info("Initializing AppContainer on persistent worker loop...")
            
            # 🌟 FIX: Manually open the database connection pools for the Celery Worker
            logger.info("🔌 Opening Genome PostgreSQL connection pool in Celery...")
            await genome_connection_pool.open()
            
            logger.info("🔌 Opening LangGraph PostgreSQL connection pool in Celery...")
            await langgraph_connection_pool.open()

            # Now that pools are open, initialize the container
            await container.initialize()
            self._container_ready = True
            
        return container

    def execute_async(self, coro):
        """Helper method to execute async code on the persistent loop."""
        return self.worker_loop.run_until_complete(coro)


@celery.task(name="llm.tasks.ingest_knowledge", bind=True, base=AsyncBioinformaticsTask)
def celery_ingest_graph_knowledge(self, source_text: str, source_metadata: Optional[Dict[str, Any]] = None):
    logger.info(f"Celery picked up graph ingestion task. Text length: {len(source_text)}")

    async def async_runner():
        # 🌟 FIX 2: Await the container initialization INSIDE the async block
        container = await self.get_ready_container_async()
        
        await container.graph_ingestion_service.ingest_knowledge(
            source_text=source_text,
            source_metadata=source_metadata
        )

    try:
        # Run everything in ONE continuous loop execution
        self.execute_async(async_runner())
    except Exception as exc:
        logger.error(f"Celery ingestion task failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=10)


@celery.task(name="llm.tasks.process_document_ingestion", bind=True, base=AsyncBioinformaticsTask)
def process_document_ingestion(self, target_uri: str, metadata: dict):
    settings = get_settings()

    async def async_run():
        # 🌟 FIX 3: Await the container initialization INSIDE the async block
        container = await self.get_ready_container_async()

        local_file_path = target_uri
        is_remote = target_uri.startswith("s3://")
        s3_bucket, s3_key = "", ""

        chunks = None
        raw_chunks = None

        try:
            self.update_state(state='PROGRESS', meta={'message': 'Initializing download...'})
            
            if is_remote:
                parts = target_uri.replace("s3://", "").split("/", 1)
                s3_bucket, s3_key = parts[0], parts[1]
                ext = os.path.splitext(s3_key)[1]
                local_file_path = f"/tmp/worker_{uuid.uuid4()}{ext}"
                
                rustfs_client = cast(
                    AsyncContextManager[S3Client],
                    container.rustfs_session.client(
                        's3',
                        endpoint_url=settings.rustfs_endpoint_url,
                        aws_access_key_id=settings.rustfs_access_key_id,
                        aws_secret_access_key=settings.rustfs_secret_access_key,
                        region_name=settings.rustfs_region_name
                    )
                )

                async with rustfs_client as s3_client:
                    await s3_client.download_file(s3_bucket, s3_key, local_file_path)

            self.update_state(state='PROGRESS', meta={'message': 'Parsing document with Docling...'})
            chunks = container.document_processor.process_and_get_chunks(local_file_path)
            total_chunks = len(chunks)
            
            BATCH_SIZE = 20     # Number of chunks processed at the same time (adjust based on your Gemini API tier)
            DELAY_BETWEEN_BATCHES = 5 # Delay between batches to avoid rate limiting

            for i in range(0, total_chunks, BATCH_SIZE):
                batch = chunks[i : i + BATCH_SIZE]
                
                self.update_state(state='PROGRESS', meta={
                    'message': f'Ingesting batch {i//BATCH_SIZE + 1} (Chunks {i+1} to min({i+BATCH_SIZE}, total_chunks))',
                    'current': min(i + BATCH_SIZE, total_chunks),
                    'total': total_chunks
                })

                # Create a list of tasks to run in parallel
                tasks = []
                for j, chunk in enumerate(batch):
                    chunk_index = i + j
                    task = container.graph_ingestion_service.ingest_knowledge(
                        source_text=chunk.page_content,
                        source_metadata={
                            **metadata, 
                            "tool": "manual_document_upload", 
                            "chunk_index": chunk_index
                        }
                    )
                    tasks.append(task)

                # Run all tasks in the batch concurrently
                # return_exceptions=True prevents crashes: if one chunk fails, others can still succeed
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Log any errors that occurred in the batch
                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"[Task {self.request.id}] Failed to ingest chunk {i + j}: {str(result)}")

                # Pause between batches to avoid being rate-limited by the LLM provider
                if i + BATCH_SIZE < total_chunks:
                    await asyncio.sleep(DELAY_BETWEEN_BATCHES)

            return {
                "status": "success", 
                "message": "Ingestion complete.",
                "chunks_processed": total_chunks
            }

        except Exception as e:
            logger.error(f"[Task {self.request.id}] Fatal Error: {str(e)}")
            raise e

        finally:
            self.update_state(state='CLEANUP', meta={'message': 'Cleaning up temporary files...'})
            
            if is_remote and os.path.exists(local_file_path):
                os.remove(local_file_path)

            if chunks is not None:
                del chunks
            if raw_chunks is not None:
                del raw_chunks
            gc.collect()

    # Run everything in ONE continuous loop execution
    return self.execute_async(async_run())

from celery.signals import worker_process_shutdown

@worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """Gracefully close database pools when the Celery worker shuts down."""
    
    # We need to run the async close methods in the synchronous shutdown hook
    async def close_pools():
        logger.info("🛑 Shutting down Celery worker process...")
        try:
            await genome_connection_pool.close()
            logger.info("🔌 Closed Genome pool.")
        except Exception:
            pass
            
        try:
            await langgraph_connection_pool.close()
            logger.info("🔌 Closed LangGraph pool.")
        except Exception:
            pass

    # Execute the shutdown on the worker's persistent loop if it exists
    loop = asyncio.get_event_loop()
    if loop and not loop.is_closed():
        loop.run_until_complete(close_pools())