import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.configs.storage.databases import userdata_connection_pool, langgraph_connection_pool
from app.models.user.user_project import UserProject
from app.common.constants import SYSTEM_OWNER_ID

class ProjectService:
    """Handles CRUD for user projects and thread management."""
    
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
                # Collect kwargs into a dict
                return UserProject(**row)
            return None

    async def get_project_threads(self, project_id: uuid.UUID) -> List[Dict[str, Any]]:
        async with langgraph_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT thread_id as id, project_id, title, created_at FROM chat_threads WHERE project_id = %s ORDER BY created_at DESC",
                (project_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]