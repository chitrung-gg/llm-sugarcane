import os
from datetime import datetime, timedelta
from typing import Any
from airflow.sdk import dag, task, get_current_context

# 🌟 Fetch paths dynamically from the worker's environment (.env)
LLM_PYTHON_BIN = os.getenv("LLM_PYTHON_BIN", "/home/cocogoat/miniconda3/envs/llm-sugarcane/bin/python")
LLM_PROJECT_DIR = os.getenv("LLM_PROJECT_DIR", "/home/cocogoat/Data/Repositories/llm-sugarcane/agent")

# # 🟢 THE FIX: Create a quarantined environment dictionary for the subprocess
# # We copy the system environment but strictly overwrite the PYTHONPATH 
# # so it never sees the 'genome-hub' folders and avoids the 'app' module collision.
# clean_env = os.environ.copy()
# clean_env["PYTHONPATH"] = LLM_PROJECT_DIR


DEFAULT_ARGS = {
    'owner': 'genome_hub',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

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

    # 1. Native Airflow Task to extract the configuration
    # Note: Removed the invalid 'python=' argument from this standard task
    @task(queue="ingest_knowledge_queue", pool="etl_pool")
    def get_dag_run_conf(**kwargs) -> dict:
        context = get_current_context()
        dag_run = context.get('dag_run')
        return (dag_run.conf or {}) if dag_run else {}

    # 2. External Task: Single Node Ingestion
    # 🟢 Notice the env=clean_env argument injected here
    @task.external_python(python=LLM_PYTHON_BIN, queue="ingest_knowledge_queue", pool="etl_pool", env_vars={"PYTHONPATH": LLM_PROJECT_DIR})
    def ingest_single_knowledge_node(conf: dict, project_dir: str):
        import asyncio
        import uuid
        import logging
        from dotenv import load_dotenv
        
        # Because the env is clean, we don't need any sys.path hacks.
        # Just load the environment variables directly.
        load_dotenv(f"{project_dir}/.env")

        source_text = conf.get("source_text")
        source_metadata = conf.get("source_metadata", {})

        if not source_text:
            logging.info("No source_text provided. Skipping single knowledge ingestion.")
            return "SKIPPED"

        async def async_runner():
            # 🟢 Python is now blind to genome-hub, so these native imports will work perfectly!
            from app.common.constants import SYSTEM_OWNER_ID
            from app.core.app_container import get_container
            from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool
            
            await genome_connection_pool.open()
            await langgraph_connection_pool.open()
            
            container = get_container()
            await container.initialize()
            
            meta = source_metadata or {}
            owner_id_str = meta.get("owner_id")
            owner_id = uuid.UUID(owner_id_str) if owner_id_str and owner_id_str != "SYSTEM" else SYSTEM_OWNER_ID

            await container.graph_ingestion_service.ingest_knowledge(
                source_text=source_text,
                source_metadata=source_metadata,
                owner_id=owner_id,
                is_public=meta.get("is_public")
            )
            
            await genome_connection_pool.close()
            await langgraph_connection_pool.close()

        # Run the async loop inside the subprocess
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(async_runner())
        
        return "SUCCESS"

    # 🟢 NEW: External Task: Batch Node Ingestion
    @task.external_python(python=LLM_PYTHON_BIN, queue="ingest_knowledge_queue", pool="etl_pool", env_vars={"PYTHONPATH": LLM_PROJECT_DIR})
    def ingest_batch_knowledge_nodes(conf: dict, project_dir: str):
        import asyncio
        import uuid
        import logging
        from dotenv import load_dotenv
        
        load_dotenv(f"{project_dir}/.env")

        batch = conf.get("batch") # Expected: List[dict(source_text, source_metadata)]

        if not batch:
            logging.info("No batch provided. Skipping batch knowledge ingestion.")
            return "SKIPPED"

        async def async_runner():
            from app.common.constants import SYSTEM_OWNER_ID
            from app.core.app_container import get_container
            from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool
            
            await genome_connection_pool.open()
            await langgraph_connection_pool.open()
            
            container = get_container()
            await container.initialize()
            
            # Extract common parameters from the first item
            first_meta = batch[0].get("source_metadata", {})
            owner_id_str = first_meta.get("owner_id")
            owner_id = uuid.UUID(owner_id_str) if owner_id_str and owner_id_str != "SYSTEM" else SYSTEM_OWNER_ID
            
            source_texts = [item.get("source_text") for item in batch]

            await container.graph_ingestion_service.ingest_knowledge_batch(
                source_texts=source_texts,
                source_metadata=first_meta, # Shared meta for now
                owner_id=owner_id,
                is_public=first_meta.get("is_public")
            )
            
            await genome_connection_pool.close()
            await langgraph_connection_pool.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(async_runner())
        
        return "SUCCESS"

    # 3. External Task: Document Ingestion
    # 🟢 Notice the env=clean_env argument injected here as well
    @task.external_python(python=LLM_PYTHON_BIN, queue="ingest_knowledge_queue", pool="etl_pool", env_vars={"PYTHONPATH": LLM_PROJECT_DIR})
    def process_document_ingestion(conf: dict, project_dir: str):
        import asyncio
        import uuid
        import os
        import ast
        import logging
        from typing import cast, AsyncContextManager
        from dotenv import load_dotenv

        load_dotenv(f"{project_dir}/.env")

        target_uri = conf.get("target_uri")
        metadata = conf.get("metadata", {})

        if not target_uri:
            logging.info("No target_uri provided. Skipping document ingestion.")
            return "SKIPPED"

        async def async_run():
            # 🟢 Clean imports!
            from app.common.constants import SYSTEM_OWNER_ID
            from app.core.app_container import get_container
            from app.configs.settings.settings import get_settings
            from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool
            
            # Local import for S3 typing within the subprocess
            from types_aiobotocore_s3 import S3Client
            
            settings = get_settings()
            
            await genome_connection_pool.open()
            await langgraph_connection_pool.open()
            
            container = get_container()
            await container.initialize()

            local_file_path = target_uri
            is_remote = target_uri.startswith("s3://")
            s3_bucket, s3_key = "", ""
            chunks = None

            try:
                if is_remote:
                    logging.info(f"Downloading remote file: {target_uri}")
                    parts = target_uri.replace("s3://", "").split("/", 1)
                    s3_bucket, s3_key = parts[0], parts[1]
                    
                    # 🟢 Extract the unique filename from S3 and save directly to /tmp
                    original_filename = os.path.basename(s3_key)
                    local_file_path = f"/tmp/{original_filename}"
                    
                    # Force the filename into the metadata for the graph/vector store
                    metadata["source_filename"] = original_filename
                    
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

                logging.info(f'Parsing document {local_file_path} with Docling...')
                chunks = container.document_processor.process_and_get_chunks(local_file_path)
                total_chunks = len(chunks)
                
                BATCH_SIZE = settings.INGESTION_BATCH_SIZE # Optimized from 8
                DELAY_BETWEEN_BATCHES = settings.INGESTION_DELAY_BETWEEN_BATCHES # Reduced from 30 as batching is more efficient
                pending_chunks = [(i, chunk) for i, chunk in enumerate(chunks)]

                while pending_chunks:
                    current_batch = pending_chunks[:BATCH_SIZE]
                    pending_chunks = pending_chunks[BATCH_SIZE:]
                    
                    current_count = total_chunks - len(pending_chunks)
                    percent = round((current_count / total_chunks) * 100, 2)
                    logging.info(f"Ingesting batch: {current_count}/{total_chunks} chunks processing ({percent}%)")

                    # 🟢 Using the new batch ingestion method to reduce LLM calls!
                    owner_id_str = metadata.get("owner_id")
                    owner_id = uuid.UUID(owner_id_str) if owner_id_str and owner_id_str != "SYSTEM" else SYSTEM_OWNER_ID
                    is_public = metadata.get("is_public")
                    
                    try:
                        texts = [chunk.page_content for _, chunk in current_batch]
                        
                        await container.graph_ingestion_service.ingest_knowledge_batch(
                            source_texts=texts,
                            source_metadata={
                                **metadata, 
                                "tool": "manual_document_upload",
                                "batch_size": len(texts)
                            },
                            owner_id=owner_id,
                            is_public=is_public
                        )
                    except Exception as e:
                        logging.error(f"Batch ingestion failed: {e}")

                    if pending_chunks:
                        await asyncio.sleep(DELAY_BETWEEN_BATCHES)

                logging.info("Ingestion complete.")
                
            finally:
                if is_remote and os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    
                await genome_connection_pool.close()
                await langgraph_connection_pool.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(async_run())
        
        return "SUCCESS"

    # 4. Tie the DAG together
    dag_config: Any = get_dag_run_conf()
    
    t_ingest_single = ingest_single_knowledge_node(
        conf=dag_config, 
        project_dir=LLM_PROJECT_DIR
    )

    t_ingest_batch = ingest_batch_knowledge_nodes(
        conf=dag_config,
        project_dir=LLM_PROJECT_DIR
    )
    
    t_ingest_doc = process_document_ingestion(
        conf=dag_config, 
        project_dir=LLM_PROJECT_DIR
    )

# Register the DAG to a global variable so Airflow's parser detects it
dag_instance = knowledge_ingestion_pipeline()