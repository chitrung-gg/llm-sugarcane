import asyncio
import gzip
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, AsyncContextManager, cast

import aioboto3
import aiofiles
from fastapi import HTTPException, UploadFile
from loguru import logger
from types_aiobotocore_s3 import S3Client

from app.utils.files.files_classifier import is_genomic_file, is_knowledge_file
from app.utils.files.files_validator import validate_genomic_file, validate_knowledge_file, extract_file_sample
from app.common.constants import UploadedFileType
from app.configs.settings.settings import get_settings


class FileIngestionService:
    """
    Handles all file I/O and asynchronous background uploads.
    Uses deterministic extension/magic-byte routing (No LLMs).
    """

    def __init__(self, rustfs_session: aioboto3.Session):
        # 🌟 LLM Service dependency completely removed
        self.rustfs_session = rustfs_session
        self.settings = get_settings()
        self._pending_uploads: Dict[str, asyncio.Task] = {}

    async def process_uploads(
        self, 
        files: List[UploadFile]
    ) -> List[Dict]:
        """
        Saves files, routes them deterministically, dispatches large files 
        to S3 background threads, and returns clean metadata for the AgentService.
        """
        uploaded_files_meta = []
        if not files:
            return uploaded_files_meta

        temp_dir = Path("/tmp/sugarcane_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            original_filename = Path(file.filename or f"unnamed_{uuid.uuid4().hex[:6]}").name
            file_id = str(uuid.uuid4())
            safe_filename = f"{file_id}_{original_filename}"
            temp_path = temp_dir / safe_filename
            
            dispatched_to_background = False

            try:
                # 1. Non-blocking Local Save
                async with aiofiles.open(temp_path, 'wb') as out_file:
                    while chunk := await file.read(1024 * 1024):  # 1MB chunks
                        await out_file.write(chunk)

                if temp_path.stat().st_size == 0:
                    raise HTTPException(400, f"File {original_filename} is empty.")

                # 2. Deterministic Routing
                if is_genomic_file(original_filename):
                    is_valid, error_msg = validate_genomic_file(temp_path, original_filename)
                    if not is_valid:
                        raise HTTPException(400, f"Genomic Validation Failed for {original_filename}: {error_msg}")
                    
                    file_size_bytes = temp_path.stat().st_size
                    
                    if file_size_bytes < 10 * 1024: # Under 10KB, keep in memory
                        raw_sequence = temp_path.read_text(encoding="utf-8", errors="ignore").strip()
                        uploaded_files_meta.append({
                            "file_id": file_id,
                            "file_name": original_filename,
                            "file_type": UploadedFileType.MD,
                            "local_content": raw_sequence,
                            "description": "Pass local_content to tools."
                        })
                    else:
                        # Heavy File: Dispatch to S3 background thread
                        rustfs_uri, final_name = self._generate_s3_metadata(original_filename, file_id)
                        
                        upload_task = asyncio.create_task(
                            self._safe_background_upload(temp_path, original_filename, rustfs_uri)
                        )
                        self._pending_uploads[rustfs_uri] = upload_task
                        dispatched_to_background = True
                        
                        uploaded_files_meta.append({
                            "file_id": file_id, "file_name": final_name, "rustfs_uri": rustfs_uri,
                            "file_type": UploadedFileType.GENOMIC_DATASET, 
                            "description": "Genomic dataset. Pass the rustfs_uri to tools."
                        })

                elif is_knowledge_file(original_filename):
                    is_valid, error_msg = validate_knowledge_file(temp_path, original_filename)
                    if not is_valid:
                        raise HTTPException(400, f"Document Validation Failed for {original_filename}: {error_msg}")
                    
                    # Store file path so AgentService/Docling can parse it
                    uploaded_files_meta.append({
                        "file_id": file_id, "file_name": original_filename, "file_path": str(temp_path),
                        "file_type": UploadedFileType.CONTEXT_DOCUMENT,
                        "description": "Requires parsing."
                    })

                else:
                    # If it fails both checks, reject it immediately
                    raise HTTPException(400, f"Unsupported file type: {original_filename}")

            except Exception as e:
                logger.error(f"File preprocessing failed for {original_filename}: {e}")
                # Ensure cleanup on immediate failure
                if temp_path.exists():
                    await asyncio.to_thread(temp_path.unlink)
                raise
                
            finally:
                # 🌟 STRICT CLEANUP: Only delete here if NOT managed by background thread
                # Note: Knowledge documents are kept on disk temporarily for the LangGraph parsers to read
                if not dispatched_to_background and not is_knowledge_file(original_filename):
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except Exception as e:
                            logger.error(f"Failed to clean up temp file {temp_path}: {e}")

        return uploaded_files_meta

    async def wait_for_file_readiness(self, rustfs_uri: str, timeout: float = 600.0):
        """Pauses execution until a specific file has finished its background upload."""
        if rustfs_uri in self._pending_uploads:
            task = self._pending_uploads[rustfs_uri]
            if not task.done():
                logger.info(f"⏳ Sync: Waiting for background upload to complete: {rustfs_uri}")
                try:
                    await asyncio.wait_for(task, timeout=timeout)
                    logger.info(f"✅ Sync: File is now ready on S3: {rustfs_uri}")
                except asyncio.TimeoutError:
                    logger.error(f"❌ Sync: Timeout waiting for file readiness: {rustfs_uri}")
                except Exception as e:
                    logger.error(f"❌ Sync: Error during background upload readiness check: {e}")

    # -------------------------------------------------------------------------
    # Internal Private Methods
    # -------------------------------------------------------------------------

    def _generate_s3_metadata(self, original_filename: str, file_id: str) -> tuple[str, str]:
        bucket_name = self.settings.rustfs_users_bucket
        is_gz = original_filename.endswith(".gz")
        final_filename = original_filename if is_gz else f"{original_filename}.gz"
        safe_filename = f"{file_id}_{final_filename}"
        
        return f"s3://{bucket_name}/{safe_filename}", final_filename

    async def _safe_background_upload(self, temp_path: Path, original_filename: str, rustfs_uri: str):
        try:
            await self._compress_and_upload_to_s3(temp_path, original_filename, rustfs_uri)
        except Exception as e:
            logger.error(f"Background upload completely failed for {original_filename}: {e}")
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
                gz_path = temp_path.with_suffix(temp_path.suffix + '.gz')
                if gz_path.exists():
                    gz_path.unlink()
            except Exception as e:
                logger.error(f"Background cleanup failed for {original_filename}: {e}")
                
            self._pending_uploads.pop(rustfs_uri, None)

    async def _compress_and_upload_to_s3(self, temp_path: Path, original_filename: str, target_uri: str):
        uri_parts = target_uri.replace("s3://", "").split("/", 1)
        bucket_name = uri_parts[0]
        safe_filename = uri_parts[1]
        
        is_already_gz = temp_path.name.endswith(".gz")
        upload_path = temp_path

        if not is_already_gz:
            compressed_temp_path = temp_path.with_suffix(temp_path.suffix + '.gz')
            logger.info(f"Compressing {original_filename} in a background thread...")

            def _sync_compress(in_path: Path, out_path: Path):
                with open(in_path, 'rb') as f_in:
                    with gzip.open(out_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

            await asyncio.to_thread(_sync_compress, temp_path, compressed_temp_path)
            upload_path = compressed_temp_path

        logger.info(f"Background: Uploading {safe_filename} to RustFS bucket: {bucket_name}")

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
            try:
                await s3_client.head_bucket(Bucket=bucket_name)
            except Exception:
                logger.warning(f"Background: Bucket '{bucket_name}' not found. Creating...")
                try:
                    await s3_client.create_bucket(Bucket=bucket_name)
                except Exception as create_err:
                    logger.error(f"Background: Failed to create bucket: {create_err}")
                    return

            await asyncio.wait_for(
                s3_client.upload_file(str(upload_path), bucket_name, safe_filename),
                timeout=600 
            )
            logger.info(f"Background: ✅ Upload complete for {original_filename}")