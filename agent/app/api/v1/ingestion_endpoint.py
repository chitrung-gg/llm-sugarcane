import asyncio
from importlib.metadata import files
from typing import List
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from loguru import logger
from app.utils.pipelines.airflow_client import get_airflow_run_status
from app.core.dependencies import get_knowledge_service
from app.core.vector_store.vector_store import VectorStoreType
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.services.knowledge.knowledge_service import KnowledgeService
from app.configs.settings.settings import get_settings

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
    Checks the status of an Airflow ingestion task (previously Celery).
    We map Airflow states back to Celery-like states for frontend compatibility.
    """
    # Assuming this endpoint is checking the document ingestion DAG.
    # If it could be multiple DAGs, you might need to pass dag_id as a query param.
    dag_id = "knowledge_ingestion_pipeline" 
    
    try:
        # Offload the synchronous requests call to a background thread
        airflow_run = await asyncio.to_thread(
            get_airflow_run_status, 
            dag_id=dag_id, 
            dag_run_id=task_id
        )
        
        airflow_state = airflow_run.get("state", "unknown").upper()
        
        # Map Airflow state strings to Celery-like status strings
        is_ready = airflow_state in ['SUCCESS', 'FAILED']
        
        response = {
            "task_id": task_id,
            "status": airflow_state, # Will be QUEUED, RUNNING, SUCCESS, or FAILED
            "ready": is_ready,
            "successful": airflow_state == 'SUCCESS',
            "failed": airflow_state == 'FAILED',
        }

        # Add completion date if available
        if airflow_run.get("end_date"):
            response["date_done"] = airflow_run.get("end_date")

        # In Airflow, detailed errors usually live in task instances, but we can return general info
        if airflow_state == 'FAILED':
            response["error"] = "Workflow execution failed in Airflow. Check Airflow UI for detailed logs."

        return response
        
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve task status.")