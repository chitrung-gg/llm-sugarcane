import uuid
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form

from app.core.dependencies import get_project_service
from app.services.workspace.project.project_service import ProjectService
from app.models.user.user_project import UserProject
from app.common.constants import SYSTEM_OWNER_ID

router = APIRouter()


@router.post("/projects", response_model=UserProject, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(...),
    user_id: uuid.UUID = Form(SYSTEM_OWNER_ID, description="UUID of the owner"),
    description: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None, description="JSON string of project metadata"),
    project_service: ProjectService = Depends(get_project_service)
):
    parsed_metadata = None
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON for metadata")
    return await project_service.create_project(name, user_id, description, parsed_metadata)


@router.get("/projects", response_model=List[UserProject])
async def list_projects(
    user_id: Optional[uuid.UUID] = None,
    project_service: ProjectService = Depends(get_project_service)
):
    return await project_service.get_projects(user_id)


@router.get("/projects/{project_id}", response_model=UserProject)
async def get_project(
    project_id: uuid.UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    project = await project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    project_service: ProjectService = Depends(get_project_service)
):
    success = await project_service.update_project(project_id, name, description)
    return {"success": success}


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    success = await project_service.delete_project(project_id)
    return {"success": success}


@router.get("/projects/{project_id}/threads")
async def list_project_threads(
    project_id: uuid.UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    return await project_service.get_project_threads(project_id)
