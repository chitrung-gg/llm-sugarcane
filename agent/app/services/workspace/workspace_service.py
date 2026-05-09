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

    async def update_project(
        self,
        project_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        updates = []
        params = []
        if name:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        
        if not updates:
            return False
        
        params.append(project_id)
        async with userdata_connection_pool.connection() as conn:
            await conn.execute(
                f"UPDATE user_projects SET {', '.join(updates)} WHERE id = %s",
                tuple(params)
            )
            return True

    async def delete_project(self, project_id: uuid.UUID) -> bool:
        async with userdata_connection_pool.connection() as conn:
            await conn.execute("DELETE FROM user_projects WHERE id = %s", (project_id,))
            return True

    async def get_projects(self, owner_id: Optional[uuid.UUID] = None) -> List[UserProject]:
        async with userdata_connection_pool.connection() as conn:
            query = "SELECT id, owner_id, name, description, dataset_metadata, created_at FROM user_projects"
            params = []
            if owner_id:
                query += " WHERE owner_id = %s"
                params.append(owner_id)
            
            cursor = await conn.execute(query, tuple(params))
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

    async def update_dataset(
        self,
        dataset_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        updates = []
        params = []
        if name:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        
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

    async def get_project_datasets(self, project_id: uuid.UUID) -> List[UserDataset]:
        """Returns metadata overviews for all datasets in a project."""
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, project_id, name, description, dataset_metadata, created_at FROM user_datasets WHERE project_id = %s",
                (project_id,)
            )
            dataset_rows = await cursor.fetchall()
            return [UserDataset(**row) for row in dataset_rows]

    async def get_public_dataset_ids(self) -> List[uuid.UUID]:
        """Returns IDs of all datasets marked as public."""
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM user_datasets WHERE is_public = TRUE"
            )
            rows = await cursor.fetchall()
            return [row["id"] for row in rows]

    async def get_project_dataset_ids(self, project_id: uuid.UUID) -> List[uuid.UUID]:
        """Returns IDs of all datasets belonging to a project."""
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM user_datasets WHERE project_id = %s",
                (project_id,)
            )
            rows = await cursor.fetchall()
            return [row["id"] for row in rows]

    async def get_dataset(self, dataset_id: uuid.UUID) -> Optional[UserDataset]:
        datasets = await self.get_datasets_by_ids([dataset_id])
        return datasets[0] if datasets else None

    async def get_file_by_id(self, file_id: uuid.UUID) -> Optional[UserDatasetFile]:
        """Fetches a specific file record by ID, checking both knowledge and genome tables."""
        # 1. Check user_dataset_files
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, dataset_id, file_name, file_type, rustfs_uri, file_metadata, genome_global_id, created_at FROM user_dataset_files WHERE id = %s",
                (file_id,)
            )
            row = await cursor.fetchone()
            if row:
                return UserDatasetFile(**row)

        # 2. Check genomes table
        async with genome_connection_pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT global_id as id, dataset_id, name as file_name, 
                       genome_path as rustfs_uri, genome_metadata as file_metadata, 
                       is_public, created_at 
                FROM genomes WHERE global_id = %s
                """,
                (file_id,)
            )
            row = await cursor.fetchone()
            if row:
                r_dict = dict(row)
                
                # 🌟 Dynamically map to the correct Enum based on the DB flag
                mapped_file_type = (
                    IngestionSourceType.SYSTEM_REFERENCE_GENOME 
                    if r_dict.get("is_public") 
                    else IngestionSourceType.USER_PRIVATE_GENOME
                )

                return UserDatasetFile(
                    id=r_dict["id"],
                    dataset_id=r_dict["dataset_id"],
                    file_name=r_dict["file_name"],
                    file_type=mapped_file_type,
                    rustfs_uri=r_dict["rustfs_uri"] or "No primary path",
                    file_metadata=r_dict["file_metadata"],
                    created_at=r_dict["created_at"],
                    genome_global_id=r_dict["id"]
                )
                
        return None

    async def get_datasets_by_ids(self, dataset_ids: List[uuid.UUID]) -> List[UserDataset]:
        """Fetches multiple datasets and ALL their files in exactly 3 queries."""
        if not dataset_ids:
            return []
        
        datasets_map: Dict[uuid.UUID, UserDataset] = {}
        
        # 1. Fetch Dataset Containers (Query 1)
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, project_id, name, description, dataset_metadata, is_public, created_at FROM user_datasets WHERE id = ANY(%s)",
                (dataset_ids,)
            )
            rows = await cursor.fetchall()
            for row in rows:
                r_dict = dict(row)
                dataset = UserDataset(**r_dict)
                dataset.files = []  # Initialize empty list to avoid NoneType errors later
                datasets_map[dataset.id] = dataset

        if not datasets_map:
            return []

        # 2. Fetch ALL Files for these Datasets (Queries 2 & 3)
        all_files = await self._get_bulk_dataset_files(list(datasets_map.keys()))

        # 3. Map Files back to their Parent Datasets in memory
        for file in all_files:
            if file.dataset_id in datasets_map:
                datasets_map[file.dataset_id].files.append(file)

        return list(datasets_map.values())

    # --- Dataset File Logic ---
    async def register_dataset_file(
        self,
        file_id: uuid.UUID,
        dataset_id: uuid.UUID,
        file_name: str,
        file_type: IngestionSourceType,
        rustfs_uri: str,
        file_metadata: Optional[Dict[str, Any]] = None,
        genome_id: Optional[uuid.UUID] = None
    ) -> UserDatasetFile:
        async with userdata_connection_pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO user_dataset_files (id, dataset_id, file_name, file_type, rustfs_uri, file_metadata, genome_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    file_id, dataset_id, file_name, 
                    file_type.value, rustfs_uri, 
                    json.dumps(file_metadata) if file_metadata else None, genome_id,
                    datetime.now()
                )
            )
            return UserDatasetFile(
                id=file_id, dataset_id=dataset_id, file_name=file_name, file_type=file_type, rustfs_uri=rustfs_uri,
                file_metadata=file_metadata, genome_global_id=genome_id
            )

    async def delete_dataset_file(self, file_record_id: uuid.UUID) -> bool:
        """Deletes a file record. Does NOT delete the physical file in RustFS (S3) yet."""
        async with userdata_connection_pool.connection() as conn:
            # 1. Clean up Soft Links first (if any)
            await conn.execute("DELETE FROM knowledge_file_links WHERE file_id = %s", (file_record_id,))

            # Check docs table
            await conn.execute("DELETE FROM user_dataset_files WHERE id = %s", (file_record_id,))
            
        async with genome_connection_pool.connection() as conn:
            # Check genomes table
            await conn.execute("DELETE FROM genomes WHERE global_id = %s", (file_record_id,))
        return True

    # --- Thread Logic ---
    async def get_project_threads(self, project_id: uuid.UUID) -> List[Dict[str, Any]]:
        async with langgraph_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT thread_id as id, project_id, title, created_at FROM chat_threads WHERE project_id = %s ORDER BY created_at DESC",
                (project_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def _get_bulk_dataset_files(self, dataset_ids: List[uuid.UUID]) -> List[UserDatasetFile]:
        """Aggregates files from both databases in bulk."""
        all_files = []
        
        # Query 2: Fetch Knowledge Files AND their knowledge links
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    f.id, 
                    f.dataset_id, 
                    f.file_name, 
                    f.file_type, 
                    f.rustfs_uri, 
                    f.file_metadata, 
                    f.genome_global_id, 
                    f.created_at,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'file_id', kfl.file_id,
                                'knowledge_entity_id', kfl.knowledge_entity_id,
                                'relevance_score', kfl.relevance_score
                            )
                        ) FILTER (WHERE kfl.knowledge_entity_id IS NOT NULL), 
                        '[]'
                    ) as knowledge_links_json
                FROM user_dataset_files f
                LEFT JOIN knowledge_file_links kfl ON f.id = kfl.file_id
                WHERE f.dataset_id = ANY(%s) 
                AND f.genome_global_id IS NULL
                GROUP BY f.id
                """,
                (dataset_ids,)
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                r_dict = dict(row)
                links_data = r_dict.pop("knowledge_links_json", [])
                file_obj = UserDatasetFile(**r_dict)
                
                # Mock the relationship property for Agent Context builder
                setattr(file_obj, "knowledge_links", [
                    link for link in (links_data if isinstance(links_data, list) else json.loads(links_data))
                ])
                all_files.append(file_obj)
            
        # Query 3: Fetch Logical Genomes from Genome Schema
        async with genome_connection_pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT global_id as id, dataset_id, name as file_name, 
                       genome_path as rustfs_uri, genome_metadata as file_metadata, 
                       is_public, created_at 
                FROM genomes WHERE dataset_id = ANY(%s)
                """,
                (dataset_ids,)
            )
            rows = await cursor.fetchall()
            for row in rows:
                r_dict = dict(row)

                mapped_file_type = (
                    IngestionSourceType.SYSTEM_REFERENCE_GENOME 
                    if r_dict["is_public"] 
                    else IngestionSourceType.USER_PRIVATE_GENOME
                )

                all_files.append(UserDatasetFile(
                    id=r_dict["id"],
                    dataset_id=r_dict["dataset_id"],
                    file_name=r_dict["file_name"],
                    file_type=mapped_file_type, 
                    rustfs_uri=r_dict["rustfs_uri"] or "No primary path",
                    file_metadata=r_dict["file_metadata"],
                    created_at=r_dict["created_at"],
                    genome_global_id=r_dict["id"] 
                ))
                
        return all_files
