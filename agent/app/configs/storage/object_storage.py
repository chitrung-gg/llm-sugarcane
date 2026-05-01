import aioboto3
from typing import AsyncContextManager, cast
from types_aiobotocore_s3.client import S3Client

from app.configs.settings.settings import get_settings

settings = get_settings()

# Type hint: An async context manager that yields an S3Client
rustfs_session: aioboto3.Session = aioboto3.Session(
    aws_access_key_id=settings.RUSTFS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.RUSTFS_SECRET_ACCESS_KEY,
    region_name=settings.RUSTFS_REGION_NAME
)