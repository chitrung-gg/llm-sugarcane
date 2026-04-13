import asyncio
import gc
import os
from typing import Any, Dict, Optional, cast, AsyncContextManager
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from types_aiobotocore_s3 import S3Client

from app.configs.settings.settings import get_settings
from app.core.workers.celery import celery
from app.core.app_container import get_container
from app.services.knowledge.graph_ingestion_service import GraphIngestionService

@celery.task(name="tasks.ingest_knowledge", bind=True)
def celery_ingest_graph_knowledge(self, source_text: str, source_metadata: Optional[Dict[str, Any]] = None):
    """
    Synchronous Celery task wrapper that spins up a SINGLE async event loop 
    to initialize dependencies and execute the GraphIngestionService.
    """
    logger.info(f"Celery picked up graph ingestion task. Text length: {len(source_text)}")

    # Define a single async entrypoint so all DB connection pools 
    # are attached to the exact same event loop.
    async def async_runner():
        container = get_container()
        
        # Check if the container is initialized (catching the assertion error from your container implementation)
        try:
            _ = container.llm_service
        except AssertionError:
            logger.info("Worker process container not initialized. Initializing now...")
            await container.initialize()
            
        # Run the ingestion
        await container.graph_ingestion_service.ingest_knowledge(
            source_text=source_text,
            source_metadata=source_metadata
        )

    # Execute the async loop
    try:
        asyncio.run(async_runner())
    except Exception as exc:
        logger.error(f"Celery ingestion task failed: {str(exc)}")
        # Trigger Celery retry mechanism (countdown in seconds)
        raise self.retry(exc=exc, countdown=10)
    
    
@celery.task(name="tasks.process_document_ingestion", bind=True)
def process_document_ingestion(self, target_uri: str, metadata: dict):
    """
    Background worker to download, parse, and ingest documents into the Knowledge Graph.
    """
    async def async_run():
        container = get_container()
        settings = get_settings()
        try:
            _ = container.llm_service
        except Exception:
            logger.warning("Initializing AppContainer in Celery worker...")
            await container.initialize()

        local_file_path = target_uri
        is_remote = target_uri.startswith("s3://")
        s3_bucket, s3_key = "", ""

        # 🌟 FIX: Safely initialize variables at the highest scope
        chunks = None
        raw_chunks = None

        try:
            self.update_state(state='PROGRESS', meta={'message': 'Initializing download...'})
            
            # 1. Handle Distributed Storage Download
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
                logger.info(f"Downloaded {target_uri} to worker at {local_file_path}")

            # 2. Parse document using Docling
            self.update_state(state='PROGRESS', meta={'message': 'Parsing document with Docling...'})
            
            # If you want to use the RecursiveCharacterTextSplitter, uncomment these lines and map them:
            # raw_chunks = container.document_processor.process_and_get_chunks(local_file_path)
            # fallback_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            # chunks = fallback_splitter.split_documents(raw_chunks)
            
            # Otherwise, just use the direct processor:
            chunks = container.document_processor.process_and_get_chunks(local_file_path)

            total_chunks = len(chunks)
            logger.info(f"[Task {self.request.id}] Starting ingestion of {total_chunks} chunks.")

            # 3. Extract and Ingest into Knowledge Graph
            for i, chunk in enumerate(chunks):
                self.update_state(state='PROGRESS', meta={
                    'message': f'Ingesting chunk {i+1} of {total_chunks}',
                    'current': i + 1,
                    'total': total_chunks
                })

                try:
                    await container.graph_ingestion_service.ingest_knowledge(
                        source_text=chunk.page_content,
                        source_metadata={
                            **metadata, 
                            "tool": "manual_document_upload", # Maps to your registry key!
                            "chunk_index": i
                        }
                    )
                except Exception as chunk_err:
                    logger.error(f"[Task {self.request.id}] Failed to ingest chunk {i}: {str(chunk_err)}")

                # Circuit Breaker to prevent hitting Gemini Rate Limits
                await asyncio.sleep(4) 

            return {
                "status": "success", 
                "message": "Ingestion complete.",
                "chunks_processed": total_chunks
            }

        except Exception as e:
            logger.error(f"[Task {self.request.id}] Fatal Error: {str(e)}")
            raise e

        finally:
            # 4. GUARANTEED CLEANUP
            self.update_state(state='CLEANUP', meta={'message': 'Cleaning up temporary files...'})
            
            # Clean local worker disk
            if is_remote and os.path.exists(local_file_path):
                os.remove(local_file_path)

            # 🌟 FIX: Safe, explicit memory deletion without using locals()
            if chunks is not None:
                del chunks
            if raw_chunks is not None:
                del raw_chunks
            gc.collect()

    # Block the Celery thread until the async ingestion loop completes
    return asyncio.run(async_run())