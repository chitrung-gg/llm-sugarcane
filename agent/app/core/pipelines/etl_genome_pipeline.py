import asyncio
import logging
import uuid
import os
import ast
from datetime import datetime, timedelta
from typing import cast, AsyncContextManager
from types_aiobotocore_s3 import S3Client

from airflow.sdk import dag, task, get_current_context

DEFAULT_ARGS = {
    'owner': 'genome_hub',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

# --- Helper Function for Async Execution in Airflow ---
def _run_async(coro):
    """Helper to run an async coroutine synchronously within an Airflow worker."""
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def _get_initialized_container():
    """Helper to get an initialized app container safely."""
    from app.core.app_container import get_container
    from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool
    
    container = get_container()
    
    # Airflow workers are isolated processes; they need their own DB connections
    await genome_connection_pool.open()
    await langgraph_connection_pool.open()
    await container.initialize()
    
    return container


@dag(
    dag_id="knowledge_ingestion_pipeline",
    default_args=DEFAULT_ARGS,
    schedule=None, 
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bioinformatics", "etl", "knowledge_graph"],
    max_active_runs=2 
)
def knowledge_ingestion_pipeline():

    @task(queue="ingest_knowledge_queue", pool="etl_pool")
    def ingest_single_knowledge_node(**kwargs):
        """
        Equivalent to `celery_ingest_graph_knowledge`.
        Processes a single string of text for Graph Enrichment.
        """
        log = logging.getLogger(__name__)
        context = get_current_context()
        
        dag_run = context.get('dag_run')
        conf = (dag_run.conf or {}) if dag_run else {}
        
        source_text = conf.get("source_text")
        source_metadata = conf.get("source_metadata", {})
        
        if not source_text:
            log.info("No source_text provided. Skipping single knowledge ingestion.")
            return "SKIPPED"
            
        log.info(f"🧠 Picked up graph ingestion task. Text length: {len(source_text)}")

        async def async_runner():
            from app.common.constants import SYSTEM_OWNER_ID
            container = await _get_initialized_container()
            
            meta = source_metadata or {}
            owner_id_str = meta.get("owner_id")
            owner_id = uuid.UUID(owner_id_str) if owner_id_str and owner_id_str != "SYSTEM" else SYSTEM_OWNER_ID

            await container.graph_ingestion_service.ingest_knowledge(
                source_text=source_text,
                source_metadata=source_metadata,
                owner_id=owner_id,
                is_public=meta.get("is_public")
            )
            
            # Clean up connections
            from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool
            await genome_connection_pool.close()
            await langgraph_connection_pool.close()

        _run_async(async_runner())
        return "SUCCESS"


    @task(queue="ingest_knowledge_queue", pool="etl_pool")
    def process_document_ingestion(**kwargs):
        """
        Equivalent to `process_document_ingestion`.
        Downloads a document, chunks it, and ingests in batches.
        """
        log = logging.getLogger(__name__)
        context = get_current_context()
        
        dag_run = context.get('dag_run')
        conf = (dag_run.conf or {}) if dag_run else {}
        
        target_uri = conf.get("target_uri")
        metadata = conf.get("metadata", {})
        
        if not target_uri:
            log.info("No target_uri provided. Skipping document ingestion.")
            return "SKIPPED"
            
        from app.configs.settings.settings import get_settings
        settings = get_settings()

        async def async_run():
            from app.common.constants import SYSTEM_OWNER_ID
            container = await _get_initialized_container()

            local_file_path = target_uri
            is_remote = target_uri.startswith("s3://")
            s3_bucket, s3_key = "", ""
            chunks = None

            try:
                if is_remote:
                    log.info(f"Downloading remote file: {target_uri}")
                    parts = target_uri.replace("s3://", "").split("/", 1)
                    s3_bucket, s3_key = parts[0], parts[1]
                    ext = os.path.splitext(s3_key)[1]
                    local_file_path = f"/tmp/airflow_worker_{uuid.uuid4()}{ext}"
                    
                    rustfs_client = cast(
                        AsyncContextManager[S3Client],
                        container.rustfs_session.client(
                            's3',
                            endpoint_url=settings.RUSTFS_ENDPOINT_URL,
                            aws_access_key_id=settings.RUSTFS_ACCESS_KEY_ID,
                            aws_secret_access_key=settings.RUSTFS_SECRET_ACCESS_KEY,
                            region_name=settings.RUSTFS_REGION_NAME
                        )
                    )

                    async with rustfs_client as s3_client:
                        await s3_client.download_file(s3_bucket, s3_key, local_file_path)

                log.info('Parsing document with Docling...')
                chunks = container.document_processor.process_and_get_chunks(local_file_path)
                total_chunks = len(chunks)
                
                BATCH_SIZE = 8
                DELAY_BETWEEN_BATCHES = 30 
                pending_chunks = [(i, chunk) for i, chunk in enumerate(chunks)]

                while pending_chunks:
                    current_batch = pending_chunks[:BATCH_SIZE]
                    pending_chunks = pending_chunks[BATCH_SIZE:]
                    
                    current_count = total_chunks - len(pending_chunks)
                    percent = round((current_count / total_chunks) * 100, 2)
                    
                    log.info(f"Ingesting batch: {current_count}/{total_chunks} chunks processed ({percent}%)")

                    tasks = []
                    owner_id_str = metadata.get("owner_id")
                    owner_id = uuid.UUID(owner_id_str) if owner_id_str and owner_id_str != "SYSTEM" else SYSTEM_OWNER_ID
                    is_public = metadata.get("is_public")

                    for chunk_index, chunk in current_batch:
                        task = container.graph_ingestion_service.ingest_knowledge(
                            source_text=chunk.page_content,
                            source_metadata={
                                **metadata, 
                                "tool": "manual_document_upload", 
                                "chunk_index": chunk_index
                            },
                            owner_id=owner_id,
                            is_public=is_public
                        )
                        tasks.append(task)

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    rate_limit_hit = False

                    for (chunk_index, chunk), result in zip(current_batch, results):
                        if isinstance(result, Exception):
                            error_type = type(result).__name__
                            error_str = str(result)
                            is_rate_limit = False
                            
                            status_code = getattr(result, 'code', None) or getattr(result, 'status_code', None)
                            if status_code == 429 or error_type in ["ResourceExhausted", "RateLimitError"]:
                                is_rate_limit = True
                            elif "{" in error_str:
                                dict_str = error_str[error_str.find("{"):]
                                try:
                                    error_data = ast.literal_eval(dict_str)
                                    err_payload = error_data.get("error", {})
                                    if err_payload.get("code") == 429 or err_payload.get("status") == "RESOURCE_EXHAUSTED":
                                        is_rate_limit = True
                                except (ValueError, SyntaxError):
                                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                                        is_rate_limit = True

                            if is_rate_limit:
                                pending_chunks.insert(0, (chunk_index, chunk))
                                rate_limit_hit = True
                            else:
                                log.error(f"Failed chunk {chunk_index}: {error_type} - {error_str}")

                    if rate_limit_hit:
                        log.warning("Hit API Rate Limit. Pausing for 60s before retrying failed chunks...")
                        await asyncio.sleep(60)
                    elif pending_chunks:
                        await asyncio.sleep(DELAY_BETWEEN_BATCHES)

                log.info("Ingestion complete.")
                
            finally:
                if is_remote and os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    
                # Clean up connections
                from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool
                await genome_connection_pool.close()
                await langgraph_connection_pool.close()

        _run_async(async_run())
        return "SUCCESS"

    t_ingest_single = ingest_single_knowledge_node()
    t_ingest_doc = process_document_ingestion()

# Register the DAG
knowledge_ingestion_pipeline()