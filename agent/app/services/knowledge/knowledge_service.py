import os
import uuid
import asyncio
import gzip
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncContextManager, cast
import aiofiles
from fastapi import UploadFile, HTTPException
from loguru import logger
import aioboto3
from types_aiobotocore_s3 import S3Client

from app.core.tools.genome_tool import execute_trigger_genome_etl
from app.utils.pipelines.airflow_client import trigger_airflow_dag
from app.configs.settings.settings import get_settings
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.core.vector_store.vector_store import VectorStoreType
from app.utils.files.files_classifier import is_genomic_file, is_knowledge_file, get_genomic_file_type
from app.utils.files.files_validator import validate_genomic_file, validate_knowledge_file
from app.services.workspace.workspace_service import WorkspaceService
from app.services.storage.storage_service import StorageService
from app.common.constants import SYSTEM_OWNER_ID

class KnowledgeService:
    """
    Handles Validation, Ingestion Registration, and high-level ingestion logic.
    Delegates raw storage tasks to StorageService.
    """

    def __init__(self, storage_service: StorageService, workspace_service: WorkspaceService):
        self.storage_service = storage_service
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
        Loops through uploaded files, validates, uploads to Storage, 
        persists metadata, and triggers async ingestion tasks.
        """
        dispatched_tasks = []
        temp_dir = Path("/tmp/sugarcane_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)

        logical_genome_id = uuid.uuid4()

        for file in files:
            if not file.filename:
                continue

            file_id = uuid.uuid4()
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
                
                is_genomic = is_genomic_file(original_filename)
                if is_genomic:
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

                # 3. Handle Compression and Storage Upload
                target_uri, final_filename = await self._prepare_and_store(
                    temp_path, 
                    original_filename,
                    str(file_id),
                    source_type
                )

                current_genome_id = logical_genome_id if is_genomic else None

                # 4. Record in Database if dataset-scoped
                if dataset_id:
                    # Extract metadata for this specific file if provided
                    this_file_meta = files_metadata.get(original_filename) if files_metadata else None
                    
                    await self.workspace_service.register_dataset_file(
                        file_id=file_id,
                        dataset_id=dataset_id,
                        file_name=final_filename,
                        file_type=source_type, 
                        rustfs_uri=target_uri,
                        file_metadata=this_file_meta,
                        genome_id=current_genome_id
                    )

                # 5. Trigger Backend ETL for Genomic Files
                if is_genomic and dataset_id:
                    logger.info(f"Triggering backend genomic ETL for: {original_filename}")
                    
                    genomic_type = get_genomic_file_type(original_filename)
                    
                    # Pass the logical_genome_id to Genome Service
                    etl_result = await execute_trigger_genome_etl(
                        genome_global_id=logical_genome_id, 
                        genome_name=original_filename, 
                        s3_uri=target_uri,
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
                conf_payload = {
                    "target_uri": target_uri,
                    "metadata": {
                        "file_id": str(file_id),
                        "original_filename": original_filename,
                        "source_type": source_type.value,
                        "vector_store": vector_store.value,
                        "owner_id": str(user_id),
                        "project_id": str(project_id) if project_id else None,
                        "dataset_id": str(dataset_id) if dataset_id else None
                    }
                }
                
                try:
                    # Fire the API call safely on a background thread
                    airflow_response = await asyncio.to_thread(
                        trigger_airflow_dag,
                        conf_payload=conf_payload,
                        dag_id="knowledge_ingestion_pipeline"
                    )
                    
                    # Airflow 2/3 returns the `dag_run_id` in the JSON response
                    dag_run_id = airflow_response.get("dag_run_id", "unknown_run_id")
                    
                    dispatched_tasks.append({
                        "task_id": dag_run_id, 
                        "status": "queued_in_airflow", 
                        "file": original_filename,
                        "target_store": vector_store.value
                    })
                except Exception as e:
                    logger.error(f"Airflow dispatch failed for {original_filename}: {e}")
                    dispatched_tasks.append({
                        "file": original_filename,
                        "status": "failed",
                        "error": str(e)
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

    async def _prepare_and_store(
        self,
        temp_path: Path, 
        original_filename: str, 
        file_id: str,
        source_type: IngestionSourceType
    ) -> tuple[str, str]:
        """Handles compression if needed and uploads to StorageService."""
        bucket_name = self.settings.RUSTFS_USERS_BUCKET
        is_already_gz = original_filename.endswith(".gz")
        
        # Only compress if it's a genomic file AND it isn't already compressed
        needs_compression = False
        if source_type in [IngestionSourceType.USER_PRIVATE_GENOME, IngestionSourceType.SYSTEM_REFERENCE_GENOME]:
            if not is_already_gz:
                needs_compression = True

        final_filename = f"{original_filename}.gz" if needs_compression else original_filename
        object_key = f"{file_id}_{final_filename}"
        
        upload_path = temp_path

        if needs_compression:
            logger.info(f"Compressing genomic file {original_filename} before S3 upload.")
            compressed_temp_path = temp_path.with_suffix(temp_path.suffix + '.gz')
            
            def _sync_compress(in_path: Path, out_path: Path):
                with open(in_path, 'rb') as f_in:
                    with gzip.open(out_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

            await asyncio.to_thread(_sync_compress, temp_path, compressed_temp_path)
            upload_path = compressed_temp_path

        # Delegate raw upload to StorageService
        target_uri = await self.storage_service.upload_file(
            local_path=upload_path,
            bucket=bucket_name,
            object_key=object_key
        )
        
        # Cleanup compressed file if created
        if needs_compression and upload_path.exists():
            try: os.unlink(upload_path)
            except Exception: pass

        return target_uri, final_filename
