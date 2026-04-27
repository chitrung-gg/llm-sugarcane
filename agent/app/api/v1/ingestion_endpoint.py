from importlib.metadata import files
from typing import List
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from app.core.dependencies import get_knowledge_service
from app.core.vector_store.vector_store import VectorStoreType
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.services.knowledge.knowledge_service import KnowledgeService
from app.configs.settings.settings import get_settings
from app.core.workers.celery import celery
from celery.result import AsyncResult

router = APIRouter()
settings = get_settings()

from app.common.constants import SYSTEM_OWNER_ID

@router.post("/file", status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    files: List[UploadFile] = File(...),
    source_type: IngestionSourceType = Form(...), 
    user_id: uuid.UUID = Form(SYSTEM_OWNER_ID, description="UUID of the user"),
    vector_store: VectorStoreType = Form(VectorStoreType.SOLID),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """
    Receives a file, streams it safely to shared storage, and triggers async ingestion.
    """
    # Delegate all business logic to the service
    return await knowledge_service.dispatch_ingestion_tasks(
        files=files,
        source_type=source_type,
        user_id=user_id,
        vector_store=vector_store
    )

@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Checks the status and progress of a background ingestion task.
    Returns comprehensive task information.
    """
    task_result = AsyncResult(task_id, app=celery)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "ready": task_result.ready(),
        "successful": task_result.successful(),
        "failed": task_result.failed(),
    }

    # date_done is available when the task has reached a terminal state
    if task_result.date_done:
        response["date_done"] = task_result.date_done.isoformat()

    if task_result.status == 'SUCCESS':
        response["result"] = task_result.result
    elif task_result.status == 'FAILURE':
        # result contains the exception instance in case of failure
        response["error"] = str(task_result.result)
        response["traceback"] = task_result.traceback
    else:
        # 'info' contains metadata passed via update_state (e.g., progress)
        # or the result if the task is finished but status is not SUCCESS/FAILURE
        response["meta"] = task_result.info

    return response
