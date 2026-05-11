import uuid
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

from app.core.dependencies import get_workspace_service, get_knowledge_service, get_storage_service
from app.services.workspace.workspace_service import WorkspaceService
from app.services.knowledge.knowledge_service import KnowledgeService
from app.services.storage.storage_service import StorageService
from app.models.user.user_project import UserProject
from app.models.user.user_dataset import UserDataset, UserDatasetFile
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
    user_id: Optional[uuid.UUID] = None,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all available projects, optionally filtered by owner."""
    return await workspace_service.get_projects(user_id)

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

@router.patch("/projects/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Update project details."""
    success = await workspace_service.update_project(project_id, name, description)
    return {"success": success}

@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Delete a project."""
    success = await workspace_service.delete_project(project_id)
    return {"success": success}

# --- Dataset Attachment & Library Endpoints ---

@router.get("/library", response_model=List[UserDataset])
async def list_library_datasets(
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all public datasets available for attachment."""
    return await workspace_service.get_available_library_datasets()

@router.post("/projects/{project_id}/attachments/{dataset_id}")
async def attach_dataset(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Attach a library dataset to a project."""
    success = await workspace_service.attach_dataset_to_project(project_id, dataset_id)
    return {"success": success}

@router.delete("/projects/{project_id}/attachments/{dataset_id}")
async def detach_dataset(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Detach a library dataset from a project."""
    success = await workspace_service.detach_dataset_from_project(project_id, dataset_id)
    return {"success": success}

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

@router.patch("/datasets/{dataset_id}")
async def update_dataset(
    dataset_id: uuid.UUID,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(None),
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Update dataset details."""
    success = await workspace_service.update_dataset(dataset_id, name, description, is_public)
    return {"success": success}

@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Delete a dataset."""
    success = await workspace_service.delete_dataset(dataset_id)
    return {"success": success}

@router.get("/datasets", response_model=List[UserDataset])
async def list_user_datasets(
    user_id: Optional[uuid.UUID] = None,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all datasets owned by a user across all projects."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    return await workspace_service.get_user_datasets(user_id)

@router.get("/projects/{project_id}/datasets", response_model=List[UserDataset])
async def list_project_datasets(
    project_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all datasets associated with a project."""
    return await workspace_service.get_project_datasets(project_id)

@router.get("/datasets/{dataset_id}/files", response_model=List[UserDatasetFile])
async def list_dataset_files(
    dataset_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all files associated with a specific dataset (Cultivar)."""
    # 1. Fetch the overarching dataset object
    dataset = await workspace_service.get_dataset(dataset_id)
    
    # 2. Handle the case where the dataset ID is invalid
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    # 3. Return ONLY the list of files to satisfy the response_model
    return dataset.files

@router.delete("/datasets/files/{file_record_id}")
async def delete_dataset_file(
    file_record_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """Delete a specific file record from a dataset."""
    success = await workspace_service.delete_dataset_file(file_record_id)
    return {"success": success}

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

@router.get("/files/download")
async def get_file_download_url(
    file_id: Optional[uuid.UUID] = None,
    s3_uri: Optional[str] = None,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    """
    Generate a pre-signed download URL for a file.
    Can be requested via file_id (from DB) or raw s3_uri (from tool results).
    """
    target_uri = s3_uri

    if file_id:
        file_record = await workspace_service.get_file_by_id(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File record not found")
        target_uri = file_record.rustfs_uri

    if not target_uri:
        raise HTTPException(status_code=400, detail="Either file_id or s3_uri must be provided")

    try:
        url = await storage_service.get_presigned_url(target_uri)
        return {"download_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")

@router.get("/projects/{project_id}/threads")
async def list_project_threads(
    project_id: uuid.UUID,
    workspace_service: WorkspaceService = Depends(get_workspace_service)
):
    """List all chat threads associated with a project."""
    return await workspace_service.get_project_threads(project_id)
