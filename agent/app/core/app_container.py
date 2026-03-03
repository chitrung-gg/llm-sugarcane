# app/core/container.py
from functools import lru_cache

from langchain_qdrant import QdrantVectorStore

from agent.app.configs.settings.settings import get_settings
from agent.app.services.llm.llm_service import LLMService
from agent.app.utils.document_processor import DocumentProcessor

from app.core.embeddings.gemini_embeddings_model import GeminiEmbeddingModel
from app.core.vector_store.vector_store import VectorStore


class AppContainer:
    """Central dependency container."""

    def __init__(self):
        self._llm_service: LLMService
        self._embedding_model: GeminiEmbeddingModel
        self._vector_store: QdrantVectorStore 
        self._document_processor: DocumentProcessor

    def initialize(self):
        print(" Initializing app container...")
        self._init_llm_service() 
        self._init_embedding_model()
        self._init_vector_store()
        self._init_document_processor()
        print(" App container ready.")

    def _init_llm_service(self):
        """Initialize LLM models with fallback chain."""
        self._llm_service = LLMService()

    def _init_embedding_model(self):
        """Initialize Gemini embedding model."""
        self._embedding_model = GeminiEmbeddingModel()

    def _init_vector_store(self):
        """Initialize Qdrant using your Custom VectorStore Wrapper."""
        settings = get_settings()

        qdrant_config = VectorStore(
            collection_name=settings.qdrant_collection_name,
            vector_size=settings.qdrant_vector_size, # 768
            url=settings.qdrant_url,
            dense_embedding=self._embedding_model 
        )
        
        self._vector_store = qdrant_config.get_vector_store()

    def _init_document_processor(self):
        """Initialize DocumentProcessor with the shared vector store."""
        self._document_processor = DocumentProcessor(
            vector_store=self._vector_store,
        )

    # --- Public accessors ---

    @property
    def llm_service(self) -> LLMService:
        assert self._llm_service, "Container not initialized"
        return self._llm_service

    @property
    def embedding_model(self) -> GeminiEmbeddingModel:
        assert self._embedding_model, "Container not initialized"
        return self._embedding_model

    @property
    def vector_store(self) -> QdrantVectorStore:
        assert self._vector_store, "Container not initialized"
        return self._vector_store

    @property
    def document_processor(self) -> DocumentProcessor:
        assert self._document_processor, "Container not initialized"
        return self._document_processor


# Singleton instance
_container = AppContainer()

def get_container() -> AppContainer:
    return _container