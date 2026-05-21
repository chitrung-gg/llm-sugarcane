import uuid
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

from app.core.dependencies import get_dataset_service, get_knowledge_service, get_storage_service
from app.services.workspace.dataset.dataset_service import DatasetService
from app.services.knowledge.knowledge_service import KnowledgeService
from app.services.storage.storage_service import StorageService
from app.models.user.user_dataset import UserDataset, UserDatasetFile
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.core.vector_store.vector_store import VectorStoreType
from app.common.constants import SYSTEM_OWNER_ID

router = APIRouter()


@router.get("/library", response_model=List[UserDataset])
async def list_library_datasets(
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    return await dataset_service.get_available_library_datasets()


@router.post("/projects/{project_id}/attachments/{dataset_id}")
async def attach_dataset(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    success = await dataset_service.attach_dataset_to_project(project_id, dataset_id)
    return {"success": success}


@router.delete("/projects/{project_id}/attachments/{dataset_id}")
async def detach_dataset(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    success = await dataset_service.detach_dataset_from_project(project_id, dataset_id)
    return {"success": success}


@router.post("/projects/{project_id}/datasets", response_model=UserDataset, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    project_id: uuid.UUID,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    dataset_metadata: Optional[str] = Form(None, description="JSON string of dataset metadata"),
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    parsed_metadata = None
    if dataset_metadata:
        try:
            parsed_metadata = json.loads(dataset_metadata)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON for metadata")
    return await dataset_service.create_dataset(project_id, name, description, parsed_metadata)


@router.patch("/datasets/{dataset_id}")
async def update_dataset(
    dataset_id: uuid.UUID,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(None),
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    success = await dataset_service.update_dataset(dataset_id, name, description, is_public)
    return {"success": success}


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: uuid.UUID,
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    success = await dataset_service.delete_dataset(dataset_id)
    return {"success": success}


@router.get("/datasets", response_model=List[UserDataset])
async def list_user_datasets(
    user_id: Optional[uuid.UUID] = None,
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    return await dataset_service.get_user_datasets(user_id)


@router.get("/projects/{project_id}/datasets", response_model=List[UserDataset])
async def list_project_datasets(
    project_id: uuid.UUID,
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    return await dataset_service.get_project_datasets(project_id)


@router.get("/datasets/{dataset_id}/files", response_model=List[UserDatasetFile])
async def list_dataset_files(
    dataset_id: uuid.UUID,
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    dataset = await dataset_service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset.files


@router.delete("/datasets/files/{file_record_id}")
async def delete_dataset_file(
    file_record_id: uuid.UUID,
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    success = await dataset_service.delete_dataset_file(file_record_id)
    return {"success": success}


@router.post("/datasets/{dataset_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_dataset_files(
    dataset_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    user_id: uuid.UUID = Form(SYSTEM_OWNER_ID, description="UUID of the user"),
    files_metadata: Optional[str] = Form(None, description="JSON mapping of filename to metadata"),
    source_type: IngestionSourceType = Form(IngestionSourceType.USER_PRIVATE_GENOME),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    dataset_service: DatasetService = Depends(get_dataset_service)
):
    dataset = await dataset_service.get_dataset(dataset_id)
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
    dataset_service: DatasetService = Depends(get_dataset_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    target_uri = s3_uri

    if file_id:
        file_record = await dataset_service.get_file_by_id(file_id)
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
