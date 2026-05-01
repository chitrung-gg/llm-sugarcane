import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import json

from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.configs.storage.databases import userdata_connection_pool, langgraph_connection_pool, genome_connection_pool
from app.models.user.user_project import UserProject
from app.models.user.user_dataset import UserDataset, UserDatasetFile
from app.common.constants import SYSTEM_OWNER_ID, UploadedFileType

class WorkspaceService:
    """Handles CRUD for user projects, datasets (cultivars), and files."""
    
    def __init__(self):
        pass

    # --- Project Logic ---
    async def create_project(
        self, 
        name: str, 
        owner_id: uuid.UUID = SYSTEM_OWNER_ID,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UserProject:
        async with userdata_connection_pool.connection() as conn:
            project_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO user_projects (id, owner_id, name, description, dataset_metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (project_id, owner_id, name, description, json.dumps(metadata) if metadata else None, datetime.now())
            )
            return UserProject(id=project_id, owner_id=owner_id, name=name, description=description, dataset_metadata=metadata)

    async def get_projects(self) -> List[UserProject]:
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute("SELECT id, name, description, dataset_metadata, created_at FROM user_projects")
            rows = await cursor.fetchall()
            return [UserProject(**row) for row in rows]

    async def get_project(self, project_id: uuid.UUID) -> Optional[UserProject]:
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, description, dataset_metadata, created_at FROM user_projects WHERE id = %s",
                (project_id,)
            )
            row = await cursor.fetchone()
            if row:
                return UserProject(**row)
            return None

    # --- Dataset (Cultivar) Logic ---
    async def create_dataset(
        self, 
        project_id: uuid.UUID, 
        name: str, 
        description: Optional[str] = None,
        dataset_metadata: Optional[Dict[str, Any]] = None
    ) -> UserDataset:
        async with userdata_connection_pool.connection() as conn:
            dataset_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO user_datasets (id, project_id, name, description, dataset_metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    dataset_id, project_id, name, description, 
                    json.dumps(dataset_metadata) if dataset_metadata else None,
                    datetime.now()
                )
            )
            return UserDataset(
                id=dataset_id, project_id=project_id, name=name, 
                description=description, dataset_metadata=dataset_metadata
            )

    async def get_project_datasets(self, project_id: uuid.UUID) -> List[UserDataset]:
        """Returns metadata overviews for all datasets in a project."""
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, project_id, name, description, dataset_metadata, created_at FROM user_datasets WHERE project_id = %s",
                (project_id,)
            )
            dataset_rows = await cursor.fetchall()
            return [UserDataset(**row) for row in dataset_rows]

    async def get_dataset(self, dataset_id: uuid.UUID) -> Optional[UserDataset]:
        async with userdata_connection_pool.connection() as conn:
            # 1. Fetch the dataset container
            cursor = await conn.execute(
                "SELECT id, project_id, name, description, dataset_metadata, created_at FROM user_datasets WHERE id = %s",
                (dataset_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            
            dataset = UserDataset(**row)
            # 2. Fetch its files from both sources
            dataset.files = await self.get_dataset_files(dataset_id)
            return dataset

    async def get_dataset_files(self, dataset_id: uuid.UUID) -> List[UserDatasetFile]:
        """Aggregates files from both user_dataset_files and genomes tables."""
        all_files = []
        
        # 1. Fetch from user_dataset_files (Knowledge/Documents)
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, dataset_id, file_id, file_name, file_type, rustfs_uri, file_metadata, created_at FROM user_dataset_files WHERE dataset_id = %s",
                (dataset_id,)
            )
            rows = await cursor.fetchall()
            all_files.extend([UserDatasetFile(**row) for row in rows])
            
        # 2. Fetch from genomes (Genomic Data)
        async with genome_connection_pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT global_id as id, dataset_id, global_id as file_id, name as file_name, 
                       'user_private_genome' as file_type, genome_path as rustfs_uri, 
                       genome_metadata as file_metadata, created_at 
                FROM genomes WHERE dataset_id = %s
                """,
                (dataset_id,)
            )
            rows = await cursor.fetchall()
            for row in rows:
                # Map genome record to UserDatasetFile format for frontend consistency
                all_files.append(UserDatasetFile(
                    id=row["id"],
                    dataset_id=row["dataset_id"],
                    file_id=row["file_id"],
                    file_name=row["file_name"],
                    file_type=IngestionSourceType.USER_PRIVATE_GENOME,
                    rustfs_uri=row["rustfs_uri"] or "No primary path",
                    file_metadata=row["file_metadata"],
                    created_at=row["created_at"]
                ))
        return all_files

    async def get_datasets_by_ids(self, dataset_ids: List[uuid.UUID]) -> List[UserDataset]:
        if not dataset_ids:
            return []
        
        datasets = []
        for d_id in dataset_ids:
            ds = await self.get_dataset(d_id)
            if ds:
                datasets.append(ds)
        return datasets

    # --- Dataset File Logic ---
    async def register_dataset_file(
        self,
        dataset_id: uuid.UUID,
        file_id: uuid.UUID,
        file_name: str,
        file_type: IngestionSourceType,
        rustfs_uri: str,
        file_metadata: Optional[Dict[str, Any]] = None
    ) -> UserDatasetFile:
        async with userdata_connection_pool.connection() as conn:
            record_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO user_dataset_files (id, dataset_id, file_id, file_name, file_type, rustfs_uri, file_metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record_id, dataset_id, file_id, file_name, 
                    file_type.value, rustfs_uri, 
                    json.dumps(file_metadata) if file_metadata else None,
                    datetime.now()
                )
            )
            return UserDatasetFile(
                id=record_id, dataset_id=dataset_id, file_id=file_id, 
                file_name=file_name, file_type=file_type, rustfs_uri=rustfs_uri,
                file_metadata=file_metadata
            )

    # --- Thread Logic ---
    async def get_project_threads(self, project_id: uuid.UUID) -> List[Dict[str, Any]]:
        async with langgraph_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT thread_id as id, project_id, title, created_at FROM chat_threads WHERE project_id = %s ORDER BY created_at DESC",
                (project_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
