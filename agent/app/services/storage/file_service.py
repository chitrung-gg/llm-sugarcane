import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.user.knowledge_file_link import KnowledgeFileLink
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.configs.storage.databases import userdata_connection_pool, genome_connection_pool
from app.models.user.user_dataset import UserDatasetFile

class FileService:
    """Handles CRUD operations specifically for files attached to datasets, bridging userdata and genome schemas."""

    async def get_file_by_id(self, file_id: uuid.UUID) -> Optional[UserDatasetFile]:
        """Fetches a specific file record by ID, checking both knowledge and genome tables."""
        # 1. Check user_dataset_files (Knowledge files)
        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, dataset_id, file_name, file_type, rustfs_uri, file_metadata, genome_global_id, created_at FROM user_dataset_files WHERE id = %s",
                (file_id,)
            )
            row = await cursor.fetchone()
            if row:
                return UserDatasetFile(**row)

        # 2. Check genomes table (Legacy Genome logic)
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
        """Registers a new file record into the database."""
        async with userdata_connection_pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO user_dataset_files (id, dataset_id, file_name, file_type, rustfs_uri, file_metadata, genome_global_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    file_id, dataset_id, file_name, file_type.value, rustfs_uri, 
                    json.dumps(file_metadata) if file_metadata else None, 
                    genome_id, datetime.now()
                )
            )
            return UserDatasetFile(
                id=file_id, dataset_id=dataset_id, file_name=file_name, 
                file_type=file_type, rustfs_uri=rustfs_uri,
                file_metadata=file_metadata, genome_global_id=genome_id
            )

    async def delete_dataset_file(self, file_record_id: uuid.UUID) -> bool:
        """Deletes a file record and its associated links. Does NOT delete the physical file in RustFS (S3) yet."""
        async with userdata_connection_pool.connection() as conn:
            # Clean up Soft Links first
            await conn.execute("DELETE FROM knowledge_file_links WHERE file_id = %s", (file_record_id,))
            await conn.execute("DELETE FROM user_dataset_files WHERE id = %s", (file_record_id,))
            
        async with genome_connection_pool.connection() as conn:
            # Clean up from genome schema if applicable
            await conn.execute("DELETE FROM genomes WHERE global_id = %s", (file_record_id,))
        return True

    async def get_bulk_dataset_files(self, dataset_ids: List[uuid.UUID]) -> List[UserDatasetFile]:
        """Fetches all physical files for the given dataset IDs from user_dataset_files."""
        if not dataset_ids:
            return []

        all_files = []

        async with userdata_connection_pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    f.id, f.dataset_id, f.file_name, f.file_type, f.rustfs_uri,
                    f.file_metadata, f.genome_global_id, f.created_at,
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
                GROUP BY f.id
                """,
                (dataset_ids,)
            )
            rows = await cursor.fetchall()

            for row in rows:
                r_dict = dict(row)
                links_data = r_dict.pop("knowledge_links_json", [])
                file_obj = UserDatasetFile(**r_dict)

                parsed_links = links_data if isinstance(links_data, list) else json.loads(links_data)
                link_instances = [KnowledgeFileLink(**link_dict) for link_dict in parsed_links]
                setattr(file_obj, "knowledge_links", link_instances)

                all_files.append(file_obj)

        return all_files