import asyncio
from typing import Any, Dict, Optional

from loguru import logger

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
            
        # Instantiate the service with the initialized dependencies
        ingestion_service = GraphIngestionService(
            llm_service=container.llm_service,
            vector_store=container.vector_store
        )
        
        # Run the ingestion
        await ingestion_service.ingest_knowledge(
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