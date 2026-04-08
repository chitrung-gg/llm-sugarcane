from functools import lru_cache
from typing import List

from langchain_qdrant import QdrantVectorStore
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.graph.state import CompiledStateGraph
from langchain_core.tools import BaseTool
from loguru import logger
from botocore.client import BaseClient

from app.core.tools.ncbi_eutils_tool import get_gene_metadata_by_symbol, search_literature_for_traits, search_ncbi_genome
from app.core.tools.openapi_tool import build_openapi_tools
from app.core.graph.graph import build_agent_graph
from app.configs.settings.settings import get_settings
from app.services.llm.llm_service import LLMService
from app.utils.document_processor import DocumentProcessor

from app.core.embeddings.gemini_embeddings_model import GeminiEmbeddingModel
from app.core.vector_store.vector_store import VectorStore
from app.configs.storage.object_storage import rustfs_client
from app.core.tools.genome_tool import (
    design_polyploid_primer, get_gene_detail,
    get_genes_list, list_genome_files, run_blast, run_crispor,
    run_synteny_analysis, search_genes_full
)

class AppContainer:
    """Central dependency container."""

    def __init__(self):
        self._llm_service: LLMService | None = None
        self._embedding_model: GeminiEmbeddingModel | None = None
        self._vector_store: QdrantVectorStore | None = None
        self._document_processor: DocumentProcessor | None = None
        self._searx_wrapper: SearxSearchWrapper | None = None
        self._agent_graph: CompiledStateGraph | None = None
        self._rustfs_client: BaseClient | None = None

    async def initialize(self):
        logger.info(" Initializing app container...")
        await self._init_llm_service() 
        await self._init_embedding_model()
        await self._init_vector_store()
        await self._init_document_processor()
        await self._init_searx_wrapper()
        await self._init_ncbi_tools()
        await self._init_agent_graph()
        await self._init_rustfs_client()
        logger.info(" App container ready.")

    async def _init_llm_service(self):
        """Initialize LLM models with fallback chain."""
        self._llm_service = LLMService()

    async def _init_embedding_model(self):
        """Initialize Gemini embedding model."""
        self._embedding_model = GeminiEmbeddingModel()

    async def _init_vector_store(self):
        """Initialize Qdrant using your Custom VectorStore Wrapper."""
        settings = get_settings()

        if settings.qdrant_collection_name is None:
            raise ValueError("Qdrant Collection Name is not configured")
        
        qdrant_config = VectorStore(
            collection_name=settings.qdrant_collection_name,
            vector_size=settings.qdrant_vector_size, # 768
            url=settings.qdrant_url,
            dense_embedding=self.embedding_model 
        )
        
        self._vector_store = qdrant_config.get_vector_store()

    async def _init_searx_wrapper(self):
        """Initialize SearXNG Wrapper."""
        settings = get_settings()

        if settings.searx_host is None:
            raise ValueError("SEARX_HOST is not configured")
        
        self._searx_wrapper = SearxSearchWrapper(
            searx_host=settings.searx_host.get_secret_value()
        )

    async def _init_document_processor(self):
        """Initialize DocumentProcessor with the shared vector store."""
        self._document_processor = DocumentProcessor(
            vector_store=self.vector_store,
        )

    async def _init_agent_graph(self):
        """
        Builds the LangGraph once during startup.
        
        Because each method return the name depends on the OpenAPI specs, and can be changed over time, so we should build the list dynamically
        """
        static_tools = [
            list_genome_files, get_genes_list, search_genes_full,
            get_gene_detail, run_blast, run_synteny_analysis, 
            run_crispor, design_polyploid_primer, search_literature_for_traits, get_gene_metadata_by_symbol, search_ncbi_genome
        ]
        # Combine static and dynamic tools into a dictionary
        # all_tools = {tool.name: tool for tool in static_tools + self.ncbi_tools}
        all_tools = {tool.name: tool for tool in static_tools}

        self._agent_graph = await build_agent_graph(
            llm_service=self.llm_service,
            vector_store=self.vector_store,
            searx_wrapper=self.searx_search,
            document_processor=self.document_processor, 
            available_tools=all_tools
        )

    async def _init_rustfs_client(self):
        """Initialize RustFS client (S3 compatible)"""
        self._rustfs_client = rustfs_client

    async def _init_ncbi_tools(self):
        """Initialize dynamic tools from NCBI OpenAPI spec."""
        settings = get_settings()
        api_key = settings.ncbi_api_key.get_secret_value() if settings.ncbi_api_key else None
        
        self._ncbi_tools = build_openapi_tools(
            llm=self.llm_service.get_primary_model(),
            openapi_yaml_path=settings.ncbi_openapi_yaml_path,
            api_key=api_key
        )
    

    # --- Public accessors ---

    @property
    def llm_service(self) -> LLMService:
        assert self._llm_service, "Container not initialized (LLMService missing)"
        return self._llm_service

    @property
    def embedding_model(self) -> GeminiEmbeddingModel:
        assert self._embedding_model, "Container not initialized (Embedding Model missing)"
        return self._embedding_model

    @property
    def vector_store(self) -> QdrantVectorStore:
        assert self._vector_store, "Container not initialized (QdrantVectorStore missing)"
        return self._vector_store

    @property
    def document_processor(self) -> DocumentProcessor:
        assert self._document_processor, "Container not initialized (DocumentProcessor missing)"
        return self._document_processor
    
    @property
    def searx_search(self) -> SearxSearchWrapper:
        assert self._searx_wrapper, "Container not initialized (SearxSearch missing)"
        return self._searx_wrapper
    
    @property
    def agent_graph(self) -> CompiledStateGraph:
        assert self._agent_graph, "Container not initialized (Agent Graph missing)"
        return self._agent_graph

    @property
    def rustfs_client(self) -> BaseClient:
        assert self._rustfs_client, "Container not initialized (RustFSClient missing)"
        return self._rustfs_client
    
    @property
    def ncbi_tools(self) -> List[BaseTool]:
        return self._ncbi_tools

# Singleton instance
_container = AppContainer()

def get_container() -> AppContainer:
    return _container