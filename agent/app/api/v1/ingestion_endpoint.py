from importlib.metadata import files
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from app.core.dependencies import get_knowledge_service
from app.core.vector_store.vector_store import VectorStoreType
from app.schemas.knowledge.knowledge_ingestion_schema import IngestionSourceType
from app.services.knowledge.knowledge_service import KnowledgeService
from app.configs.settings.settings import get_settings

router = APIRouter()
settings = get_settings()

@router.post("/ingest/file", status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    files: List[UploadFile] = File(...),
    source_type: IngestionSourceType = Form(...), 
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
        vector_store=vector_store
    )
