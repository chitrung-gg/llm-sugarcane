from fastapi import Depends
from langchain_qdrant import QdrantVectorStore
from langgraph.graph.state import CompiledStateGraph
from botocore.client import BaseClient

from app.services.knowledge.graph_ingestion_service import GraphIngestionService
from app.services.agent.agent_service import AgentService
from app.core.app_container import AppContainer, get_container
from app.services.llm.llm_service import LLMService
from app.utils.document_processor import DocumentProcessor


def get_llm_service(container: AppContainer = Depends(get_container)) -> LLMService:
    return container.llm_service

def get_vector_store(container: AppContainer = Depends(get_container)) -> QdrantVectorStore:
    return container.vector_store

def get_document_processor(container: AppContainer = Depends(get_container)) -> DocumentProcessor:
    return container.document_processor

def get_rustfs_client(container: AppContainer = Depends(get_container)) -> BaseClient:
    return container.rustfs_client

def get_agent_graph(container: AppContainer = Depends(get_container)) -> CompiledStateGraph:
    return container.agent_graph

def get_agent_service(container: AppContainer = Depends(get_container)) -> AgentService:
    return container.agent_service

def get_graph_ingestion_service(container: AppContainer = Depends(get_container)) -> GraphIngestionService:
    return container.graph_ingestion_service

