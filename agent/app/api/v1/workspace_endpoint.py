import uuid
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

from app.core.dependencies import get_workspace_service, get_knowledge_service
from app.services.workspace.workspace_service import WorkspaceService
from app.services.knowledge.knowledge_service import KnowledgeService
from app.models.user.user_project import UserProject
from app.models.user.user_dataset import UserDataset
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.core.vector_store.vector_store import VectorStoreType
from app.common.constants import SYSTEM_OWNER_ID

router = APIRouter()

@router.post("/projects", response_model=UserProject, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(...), 
    user_id: uuid.UUID = Form(SYSTEM_OWNER_ID, description="UUID of the owner"),
    description: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None, description="JSON string of project metadata"),
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Create a new research project."""
    parsed_metadata = None
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON for metadata")
            
    return await workspace_service.create_project(name, user_id, description, parsed_metadata)

@router.get("/projects", response_model=List[UserProject])
async def list_projects(
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all available projects."""
    return await workspace_service.get_projects()

@router.get("/projects/{project_id}", response_model=UserProject)
async def get_project(
    project_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Get details of a specific project."""
    project = await workspace_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# --- Dataset (Cultivar) Endpoints ---

@router.post("/projects/{project_id}/datasets", response_model=UserDataset, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    project_id: uuid.UUID,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    dataset_metadata: Optional[str] = Form(None, description="JSON string of dataset metadata"),
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Create a new dataset (Cultivar) container in a project."""
    parsed_metadata = None
    if dataset_metadata:
        try:
            parsed_metadata = json.loads(dataset_metadata)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON for metadata")

    return await workspace_service.create_dataset(project_id, name, description, parsed_metadata)

@router.get("/projects/{project_id}/datasets", response_model=List[UserDataset])
async def list_project_datasets(
    project_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all datasets associated with a project."""
    return await workspace_service.get_project_datasets(project_id)

@router.post("/datasets/{dataset_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_dataset_files(
    dataset_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    user_id: uuid.UUID = Form(SYSTEM_OWNER_ID, description="UUID of the user"),
    files_metadata: Optional[str] = Form(None, description="JSON mapping of filename to metadata"),
    source_type: IngestionSourceType = Form(IngestionSourceType.USER_PRIVATE_GENOME),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Upload files (GFF3, FASTA, etc.) to a specific dataset (Cultivar)."""
    # Verify dataset exists
    dataset = await workspace_service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    parsed_files_metadata = None
    if files_metadata:
        try:
            parsed_files_metadata = json.loads(files_metadata)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON for files_metadata")
        
    return await knowledge_service.dispatch_ingestion_tasks(
        files=files,
        source_type=source_type,
        vector_store=VectorStoreType.VOLATILE,
        user_id=user_id,
        project_id=dataset.project_id,
        dataset_id=dataset_id,
        files_metadata=parsed_files_metadata
    )
