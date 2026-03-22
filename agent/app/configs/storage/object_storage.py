import aioboto3
from botocore.client import BaseClient

from app.configs.settings.settings import get_settings


settings = get_settings()

rustfs_client: BaseClient = aioboto3.Session().client(
    's3',
    endpoint_url=settings.rustfs_endpoint_url,
    aws_access_key_id=settings.rustfs_access_key_id,
    aws_secret_access_key=settings.rustfs_secret_access_key,
    region_name=settings.rustfs_region_name 
)


