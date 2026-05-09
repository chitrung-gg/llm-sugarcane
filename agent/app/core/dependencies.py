from typing import AsyncContextManager
import aioboto3
from fastapi import Depends
from langchain_qdrant import QdrantVectorStore
from langgraph.graph.state import CompiledStateGraph
from types_aiobotocore_s3 import S3Client

from app.services.knowledge.knowledge_service import KnowledgeService
from app.services.ingestion.graph_ingestion_service import GraphIngestionService
from app.services.agent.agent_service import AgentService
from app.services.workspace.workspace_service import WorkspaceService
from app.services.storage.storage_service import StorageService
from app.core.app_container import AppContainer, get_container
from app.services.llm.llm_service import LLMService
from app.utils.document_processor import DocumentProcessor

def get_storage_service(container: AppContainer = Depends(get_container)) -> StorageService:
    return container.storage_service

def get_workspace_service(container: AppContainer = Depends(get_container)) -> WorkspaceService:
    return container.workspace_service


def get_llm_service(container: AppContainer = Depends(get_container)) -> LLMService:
    return container.llm_service

def get_vector_store_solid(container: AppContainer = Depends(get_container)) -> QdrantVectorStore:
    return container.vector_store_solid

def get_document_processor(container: AppContainer = Depends(get_container)) -> DocumentProcessor:
    return container.document_processor

def get_rustfs_session(container: AppContainer = Depends(get_container)) -> aioboto3.Session:
    return container.rustfs_session

def get_agent_graph(container: AppContainer = Depends(get_container)) -> CompiledStateGraph:
    return container.agent_graph

def get_agent_service(container: AppContainer = Depends(get_container)) -> AgentService:
    return container.agent_service

def get_knowledge_service(container: AppContainer = Depends(get_container)) -> KnowledgeService:
    return container.knowledge_service

def get_graph_ingestion_service(container: AppContainer = Depends(get_container)) -> GraphIngestionService:
    return container.graph_ingestion_service
