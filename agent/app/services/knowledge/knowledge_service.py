import os
import uuid
import asyncio
import gzip
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncContextManager, cast
from anyio import to_thread
import aiofiles
from fastapi import UploadFile, HTTPException
from loguru import logger
import aioboto3
from types_aiobotocore_s3 import S3Client

from app.configs.settings.settings import get_settings
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.core.vector_store.vector_store import VectorStoreType
from app.core.workers.celery import celery
from app.configs.storage.databases import userdata_connection_pool
from app.utils.files.files_classifier import is_genomic_file, is_knowledge_file, get_genomic_file_type
from app.utils.files.files_validator import validate_genomic_file, validate_knowledge_file
from app.services.workspace.workspace_service import WorkspaceService
from app.common.constants import SYSTEM_OWNER_ID
from app.core.tools.index_genome_etl import trigger_genome_indexing

class KnowledgeService:
    """
    Handles Validation, S3 Upload (with compression), DB Registration, and Ingestion Triggering.
    """

    def __init__(self, rustfs_session: aioboto3.Session, workspace_service: WorkspaceService):
        self.rustfs_session = rustfs_session
        self.workspace_service = workspace_service
        self.settings = get_settings()

    async def dispatch_ingestion_tasks(
        self, 
        files: List[UploadFile], 
        source_type: IngestionSourceType, 
        vector_store: VectorStoreType,
        user_id: uuid.UUID = SYSTEM_OWNER_ID,
        project_id: Optional[uuid.UUID] = None,
        dataset_id: Optional[uuid.UUID] = None,
        files_metadata: Optional[Dict[str, Any]] = None # Mapping of filename -> metadata dict
    ) -> dict:
        """
        Loops through uploaded files, validates, uploads to RustFS, 
        persists metadata, and triggers async ingestion tasks.
        """
        dispatched_tasks = []
        temp_dir = Path("/tmp/sugarcane_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)

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
                original_filename = Path(file.filename).name
                safe_filename = f"{file_id}_{original_filename}"
                temp_path = temp_dir / safe_filename
                
                try:
                    # 1. Save locally for validation
                    async with aiofiles.open(temp_path, 'wb') as out_file:
                        while chunk := await file.read(1024 * 1024):
                            await out_file.write(chunk)

                    # 2. Validation & Classification
                    is_valid = False
                    error_msg = "Unsupported file type."
                    
                    if is_genomic_file(original_filename):
                        is_valid, error_msg = validate_genomic_file(temp_path, original_filename)
                    elif is_knowledge_file(original_filename):
                        is_valid, error_msg = validate_knowledge_file(temp_path, original_filename)

                    if not is_valid:
                        dispatched_tasks.append({
                            "file": original_filename,
                            "status": "failed",
                            "error": f"Validation failed: {error_msg}"
                        })
                        continue

                    # 3. Compress and Upload to S3
                    target_uri, final_filename = await self._compress_and_upload(s3_client, temp_path, original_filename, file_id)

                    # 4. Record in Database if dataset-scoped
                    if dataset_id:
                        # Extract metadata for this specific file if provided
                        this_file_meta = files_metadata.get(original_filename) if files_metadata else None
                        
                        await self.workspace_service.register_dataset_file(
                            dataset_id=dataset_id,
                            file_id=uuid.UUID(file_id),
                            file_name=final_filename,
                            file_type=source_type, 
                            rustfs_uri=target_uri,
                            file_metadata=this_file_meta
                        )

                    # 5. Trigger Backend ETL for Genomic Files
                    if source_type in [IngestionSourceType.USER_PRIVATE_GENOME, IngestionSourceType.SYSTEM_REFERENCE_GENOME] and dataset_id:
                        logger.info(f"Triggering backend genomic ETL for: {original_filename}")
                        
                        genomic_type = get_genomic_file_type(original_filename)
                        
                        etl_result = await trigger_genome_indexing(
                            s3_uri=target_uri,
                            genome_name=original_filename, # User can rename later
                            file_type=genomic_type,
                            dataset_id=dataset_id,
                            is_public=(source_type == IngestionSourceType.SYSTEM_REFERENCE_GENOME),
                            user_id=user_id
                        )
                        
                        dispatched_tasks.append({
                            "file": original_filename,
                            "status": etl_result.get("status"),
                            "message": etl_result.get("message"),
                            "job_id": etl_result.get("job_id")
                        })
                        continue

                    # 6. Trigger Celery Task for Knowledge Documents
                    logger.info(f"Dispatching ingestion task for {target_uri}")
                    task = celery.send_task(
                        "llm.tasks.process_document_ingestion",
                        args=[
                            target_uri,
                            {
                                "original_filename": original_filename,
                                "source_type": source_type.value,
                                "vector_store": vector_store.value,
                                "owner_id": str(user_id),
                                "project_id": str(project_id) if project_id else None,
                                "dataset_id": str(dataset_id) if dataset_id else None
                            }
                        ],
                        queue="ingest_knowledge_queue"
                    )

                    dispatched_tasks.append({
                        "task_id": task.id, 
                        "status": "queued", 
                        "file": original_filename,
                        "target_store": vector_store.value
                    })

                except Exception as e:
                    logger.error(f"Failed to process {original_filename}: {str(e)}")
                    dispatched_tasks.append({
                        "file": original_filename,
                        "status": "failed",
                        "error": str(e)
                    })
                finally:
                    # Cleanup local temp files
                    if temp_path.exists():
                        try: os.unlink(temp_path)
                        except Exception: pass
                    file.file.close() 

        return {"results": dispatched_tasks}

    async def _compress_and_upload(self, s3_client: S3Client, temp_path: Path, original_filename: str, file_id: str) -> tuple[str, str]:
        bucket_name = self.settings.rustfs_users_bucket
        is_gz = original_filename.endswith(".gz")
        final_filename = original_filename if is_gz else f"{original_filename}.gz"
        safe_filename = f"{file_id}_{final_filename}"
        
        target_uri = f"s3://{bucket_name}/{safe_filename}"
        upload_path = temp_path

        if not is_gz:
            compressed_temp_path = temp_path.with_suffix(temp_path.suffix + '.gz')
            
            def _sync_compress(in_path: Path, out_path: Path):
                with open(in_path, 'rb') as f_in:
                    with gzip.open(out_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

            await asyncio.to_thread(_sync_compress, temp_path, compressed_temp_path)
            upload_path = compressed_temp_path

        # Ensure bucket exists
        try:
            await s3_client.head_bucket(Bucket=bucket_name)
        except Exception:
            logger.warning(f"Bucket '{bucket_name}' not found. Creating...")
            await s3_client.create_bucket(Bucket=bucket_name)

        await s3_client.upload_file(str(upload_path), bucket_name, safe_filename)
        
        # Cleanup compressed file if created
        if not is_gz and upload_path.exists():
            try: os.unlink(upload_path)
            except Exception: pass

        return target_uri, final_filename
