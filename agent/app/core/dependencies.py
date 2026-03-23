from fastapi import Depends
from langchain_qdrant import QdrantVectorStore
from langgraph.graph.state import CompiledStateGraph
from botocore.client import BaseClient

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

def get_agent_graph(container: AppContainer = Depends(get_container)) -> CompiledStateGraph:
    return container.agent_graph

def get_agent_service(container: AppContainer = Depends(get_container)) -> AgentService:
    return AgentService(
        graph=container.agent_graph,
        rustfs_client=container.rustfs_client,
        llm_service=container.llm_service
    )

def get_rustfs_client(container: AppContainer = Depends(get_container)) -> BaseClient:
    return container.rustfs_client