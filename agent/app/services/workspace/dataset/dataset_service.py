import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.services.storage.file_service import FileService
from app.models.user.knowledge_file_link import KnowledgeFileLink
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.configs.storage.databases import userdata_connection_pool, genome_connection_pool
from app.models.user.user_dataset import UserDataset, UserDatasetFile

class DatasetService:
    """Handles CRUD for datasets (cultivars), files, and project-dataset attachments."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service

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

    async def update_dataset(
        self,
        dataset_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None
    ) -> bool:
        updates = []
        params = []
        if name:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if is_public is not None:
            updates.append("is_public = %s")
            params.append(is_public)
        
        if not updates:
            return False
        
        params.append(dataset_id)
        async with userdata_connection_pool.connection() as conn:
            await conn.execute(
                f"UPDATE user_datasets SET {', '.join(updates)} WHERE id = %s",
                tuple(params)
            )
            return True

    async def delete_dataset(self, dataset_id: uuid.UUID) -> bool:
        async with userdata_connection_pool.connection() as conn:
            await conn.execute("DELETE FROM user_datasets WHERE id = %s", (dataset_id,))
            return True

    # --- Dataset Attachment Logic ---
    async def attach_dataset_to_project(self, project_id: uuid.UUID, dataset_id: uuid.UUID) -> bool:
        async with userdata_connection_pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO project_dataset_attachments (project_id, dataset_id)
                VALUES (%s, %s)
                """,
                (project_id, dataset_id)
            )
            return True

    async def detach_dataset_from_project(self, project_id: uuid.UUID, dataset_id: uuid.UUID) -> bool:
        async with userdata_connection_pool.connection() as conn:
            await conn.execute(
                "DELETE FROM project_dataset_attachments WHERE project_id = %s AND dataset_id = %s",
                (project_id, dataset_id)
            )
            return True

    # --- Fetching Datasets ---
    async def get_available_library_datasets(self) -> List[UserDataset]:
        """Returns all datasets marked as public for the Reference Library."""
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, project_id, name, description, dataset_metadata, is_public, created_at FROM user_datasets WHERE is_public = TRUE"
            )
            rows = await cursor.fetchall()
            return [UserDataset(**row) for row in rows]

    async def get_project_datasets(self, project_id: uuid.UUID) -> List[UserDataset]:
        """Returns metadata overviews for all datasets in a project, including attached system ones."""
        async with userdata_connection_pool.connection() as conn:
            # Query 1: Owned datasets
            cursor = await conn.execute(
                "SELECT id, project_id, name, description, dataset_metadata, is_public, created_at FROM user_datasets WHERE project_id = %s",
                (project_id,)
            )
            owned_rows = await cursor.fetchall()
            
            # Query 2: Attached datasets
            cursor = await conn.execute(
                """
                SELECT d.id, d.project_id, d.name, d.description, d.dataset_metadata, d.is_public, d.created_at 
                FROM user_datasets d
                JOIN project_dataset_attachments a ON d.id = a.dataset_id
                WHERE a.project_id = %s
                """,
                (project_id,)
            )
            attached_rows = await cursor.fetchall()
            
            all_datasets = [UserDataset(**row) for row in owned_rows]

            # Filter duplicate
            owned_ids = {d.id for d in all_datasets}
            for row in attached_rows:
                if row["id"] not in owned_ids:
                    all_datasets.append(UserDataset(**row))
                    
            return all_datasets

    async def get_user_datasets(self, user_id: uuid.UUID) -> List[UserDataset]:
        """Returns all datasets owned by a specific user across all their projects."""
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT d.id, d.project_id, d.name, d.description, d.dataset_metadata, d.is_public, d.created_at 
                FROM user_datasets d
                JOIN user_projects p ON d.project_id = p.id
                WHERE p.owner_id = %s
                """,
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [UserDataset(**row) for row in rows]

    async def get_public_dataset_ids(self) -> List[uuid.UUID]:
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute("SELECT id FROM user_datasets WHERE is_public = TRUE")
            rows = await cursor.fetchall()
            return [row["id"] for row in rows]

    async def get_project_dataset_ids(self, project_id: uuid.UUID) -> List[uuid.UUID]:
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute("SELECT id FROM user_datasets WHERE project_id = %s", (project_id,))
            rows = await cursor.fetchall()
            return [row["id"] for row in rows]

    async def get_dataset(self, dataset_id: uuid.UUID) -> Optional[UserDataset]:
        datasets = await self.get_datasets_by_ids([dataset_id])
        return datasets[0] if datasets else None

    async def get_file_by_id(self, file_id: uuid.UUID):
        return await self.file_service.get_file_by_id(file_id)

    async def delete_dataset_file(self, file_record_id: uuid.UUID) -> bool:
        return await self.file_service.delete_dataset_file(file_record_id)

    async def get_datasets_by_ids(self, dataset_ids: List[uuid.UUID]) -> List[UserDataset]:
        if not dataset_ids:
            return []
        
        datasets_map: Dict[uuid.UUID, UserDataset] = {}
        
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, project_id, name, description, dataset_metadata, is_public, created_at FROM user_datasets WHERE id = ANY(%s)",
                (dataset_ids,)
            )
            rows = await cursor.fetchall()
            for row in rows:
                r_dict = dict(row)
                dataset = UserDataset(**r_dict)
                dataset.files = []  
                datasets_map[dataset.id] = dataset

        if not datasets_map:
            return []

        all_files = await self.file_service.get_bulk_dataset_files(list(datasets_map.keys()))

        for file in all_files:
            if file.dataset_id in datasets_map:
                datasets_map[file.dataset_id].files.append(file)

        return list(datasets_map.values())