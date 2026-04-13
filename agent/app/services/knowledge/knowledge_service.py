import os
from typing import List, AsyncContextManager, cast
import uuid
from anyio import to_thread
from fastapi import UploadFile
from loguru import logger
import aioboto3
from types_aiobotocore_s3 import S3Client

from app.configs.settings.settings import get_settings
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.core.vector_store.vector_store import VectorStoreType
from app.core.workers.celery import celery
from botocore.client import BaseClient

class KnowledgeService:
    def __init__(self, rustfs_session: aioboto3.Session):
        self.rustfs_session = rustfs_session
        self.settings = get_settings()

    async def dispatch_ingestion_tasks(
        self, 
        files: List[UploadFile], 
        source_type: IngestionSourceType, 
        vector_store: VectorStoreType
    ) -> dict:
        """
        Loops through uploaded files, streams them to RustFS, 
        and fans out a separate Celery task for each.
        """
        allowed_exts = {".pdf", ".md", ".txt", ".fasta", ".gff"}
        bucket_name = "knowledge-genome"
        
        dispatched_tasks = []

        rustfs_client = cast(
            AsyncContextManager[S3Client],
            self.rustfs_session.client(
                "s3",
                endpoint_url=self.settings.rustfs_endpoint_url,
                aws_access_key_id=self.settings.rustfs_access_key_id,
                aws_secret_access_key=self.settings.rustfs_secret_access_key,
                region_name=self.settings.rustfs_region_name
            )
        )

        async with rustfs_client as s3_client:
            for file in files:
                if not file.filename:
                    continue

                file_id = str(uuid.uuid4())
                ext = os.path.splitext(file.filename)[1].lower()

                # 🌟 Batch-Safe Validation: Don't raise HTTPException, just record the error and continue
                if ext not in allowed_exts:
                    dispatched_tasks.append({
                        "file": file.filename,
                        "status": "failed",
                        "error": f"Unsupported file type: {ext}"
                    })
                    continue

                s3_key = f"ingestion_queue/{file_id}{ext}"
                
                try:
                    logger.info(f"Uploading {file.filename} to RustFS...")
                    
                    # Execute the blocking upload in a separate thread pool
                    await s3_client.upload_fileobj(
                        file.file, 
                        bucket_name, 
                        s3_key
                    )
                    target_uri = f"s3://{bucket_name}/{s3_key}"

                except Exception as e:
                    logger.error(f"Failed to upload {file.filename}: {str(e)}")
                    dispatched_tasks.append({
                        "file": file.filename,
                        "status": "failed",
                        "error": "Storage upload failed."
                    })
                    continue
                finally:
                    file.file.close() 

                # 🌟 Trigger a dedicated Celery Task for this specific file
                logger.info(f"Dispatching ingestion task for {target_uri}")
                task = celery.send_task(
                    "tasks.process_document_ingestion",
                    args=[
                        target_uri,
                        {
                            "original_filename": file.filename,
                            "source_type": source_type.value,
                            "vector_store": vector_store.value
                        }
                    ],
                    queue="ingest_knowledge_queue"
                )

                dispatched_tasks.append({
                    "task_id": task.id, 
                    "status": "queued", 
                    "file": file.filename,
                    "target_store": vector_store.value
                })

        return {"results": dispatched_tasks}