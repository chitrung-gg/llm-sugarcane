import os
import uuid
import asyncio
import gzip
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, AsyncContextManager, cast
from loguru import logger
import aioboto3
from types_aiobotocore_s3 import S3Client

from app.configs.settings.settings import get_settings

class StorageService:
    """
    Handles raw interactions with S3/RustFS including Upload, Download, and Bucket management.
    """

    def __init__(self, rustfs_session: aioboto3.Session):
        self.rustfs_session = rustfs_session
        self.settings = get_settings()

    def _get_client(self) -> AsyncContextManager[S3Client]:
        """Creates an async S3 client for RustFS/S3."""
        return cast(
            AsyncContextManager[S3Client],
            self.rustfs_session.client(
                "s3",
                endpoint_url=self.settings.RUSTFS_ENDPOINT_URL,
                aws_access_key_id=self.settings.RUSTFS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.RUSTFS_SECRET_ACCESS_KEY,
                region_name=self.settings.RUSTFS_REGION_NAME
            )
        )

    async def upload_file(
        self, 
        local_path: Path, 
        bucket: str, 
        object_key: str, 
        extra_args: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Uploads a local file to a specific S3 bucket/key.
        Returns the s3:// URI.
        """
        async with self._get_client() as s3_client:
            # Ensure bucket exists
            try:
                await s3_client.head_bucket(Bucket=bucket)
            except Exception:
                logger.warning(f"Bucket '{bucket}' not found. Creating...")
                await s3_client.create_bucket(Bucket=bucket)

            logger.info(f"Uploading {local_path} to s3://{bucket}/{object_key}")
            await s3_client.upload_file(str(local_path), bucket, object_key, ExtraArgs=extra_args)
            
        return f"s3://{bucket}/{object_key}"

    async def get_presigned_url(self, s3_uri: str, expires_in: int = 3600) -> str:
        """
        Generates a pre-signed URL for a specific S3 object.
        """
        bucket, key = await self._parse_s3_uri(s3_uri)
        async with self._get_client() as s3_client:
            return await s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in
            )

    async def download_file(self, s3_uri: str, local_path: Path) -> Path:
        """
        Downloads a file from S3 to a local destination.
        """
        bucket, key = await self._parse_s3_uri(s3_uri)
        
        async with self._get_client() as s3_client:
            logger.info(f"Downloading {s3_uri} to {local_path}")
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            await s3_client.download_file(bucket, key, str(local_path))
            
        return local_path

    async def delete_file(self, s3_uri: str):
        """Deletes an object from S3."""
        bucket, key = await self._parse_s3_uri(s3_uri)
        async with self._get_client() as s3_client:
            await s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted {s3_uri} from storage.")

    async def _parse_s3_uri(self, s3_uri: str) -> tuple[str, str]:
        """Parses an s3://bucket/key URI into (bucket, key)."""
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")
        
        parts = s3_uri.replace("s3://", "").split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"S3 URI missing object key: {s3_uri}")
            
        return parts[0], parts[1]

    
