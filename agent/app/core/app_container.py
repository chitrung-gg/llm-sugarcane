from functools import lru_cache
from typing import List, AsyncContextManager

import aioboto3
from langchain_neo4j import Neo4jGraph
from langchain_qdrant import QdrantVectorStore
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langfuse import Langfuse
from langgraph.graph.state import CompiledStateGraph
from langchain_core.tools import BaseTool
from loguru import logger
from types_aiobotocore_s3 import S3Client

from app.services.llm.reranker_service import RerankerService
from app.core.graph.graph import build_super_agent_graph
from app.core.tools.registry.registry_tool import get_agent_tools, register_agent_tool
from app.services.knowledge.knowledge_service import KnowledgeService
from app.services.agent.agent_service import AgentService
from app.core.tools.ncbi_eutils_tool import get_gene_metadata_by_symbol, search_literature_for_traits, search_ncbi_genome
from app.configs.settings.settings import get_settings
from app.services.llm.llm_service import LLMService
from app.utils.document_processor import DocumentProcessor
from app.services.ingestion.graph_ingestion_service import GraphIngestionService
from app.services.workspace.workspace_service import WorkspaceService
from app.services.storage.storage_service import StorageService

from app.core.embeddings.gemini_embeddings_model import GeminiEmbeddingModel
from app.core.vector_store.vector_store import VectorStore
from app.configs.storage.object_storage import rustfs_session
from app.configs.storage.databases import userdata_connection_pool
from app.core.tools.genome_tool import *
# from app.core.tools.index_genome_etl import index_new_genome
from app.core.tools.graph_rag_tool import make_graph_rag_tool

class AppContainer:
    """Central dependency container."""

    def __init__(self):
        self._langfuse_client: Langfuse | None = None
        self._llm_service: LLMService | None = None
        self._reranker_service: RerankerService | None = None
        self._agent_service: AgentService | None = None
        self._knowledge_service: KnowledgeService | None = None
        self._storage_service: StorageService | None = None
        self._graph_ingestion_service: GraphIngestionService | None = None
        self._workspace_service: WorkspaceService | None = None
        self._embedding_model: GeminiEmbeddingModel | None = None
        self._vector_store_solid: QdrantVectorStore | None = None
        self._vector_store_volatile: QdrantVectorStore | None = None
        self._document_processor: DocumentProcessor | None = None
        self._searx_wrapper: SearxSearchWrapper | None = None
        self._knowledge_graph: Neo4jGraph | None = None
        self._agent_graph: CompiledStateGraph | None = None
        self._graph_rag_tool: BaseTool | None = None
        self._rustfs_session: aioboto3.Session | None = None

    async def initialize(self):
        logger.info("🚀 Initializing app container...")
        
        # 1. Base Services & APIs
        await self._init_langfuse_client()
        await self._init_llm_service() 
        await self._init_reranker_service() 
        await self._init_rustfs_session()
        await self._init_storage_service()
        await self._init_searx_wrapper()
        
        # 2. Databases & Storage
        logger.info("📡 Connecting to Databases...")
        await self._init_embedding_model()
        logger.info("✅ Embedding model initialized.")
        await self._init_vector_store()
        logger.info("✅ Qdrant initialized.")
        await self._init_knowledge_graph()
        logger.info("✅ Neo4j initialized.")
        
        # 3. Middlewares & Processors
        await self._init_document_processor()
        await self._init_graph_ingestion_service()
        await self._init_workspace_service()

        # 4. The Graph
        logger.info("🗺️ Compiling Agent Graph...")
        await self._init_agent_graph()
        logger.info("✅ Agent Graph compiled.")
        
        # 5. Top-Level Services
        await self._init_knowledge_service() 
        await self._init_agent_service() 
        
        logger.info("✨ App container ready.")

    async def _init_langfuse_client(self):
        """Initialize the Langfuse singleton client with explicit Pydantic settings."""
        settings = get_settings()
        
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            self._langfuse_client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY.get_secret_value(),
                secret_key=settings.LANGFUSE_SECRET_KEY.get_secret_value(),
                host=settings.LANGFUSE_BASE_URL
            )
            logger.info("✅ Langfuse client initialized.")
        else:
            self._langfuse_client = None
            logger.warning("⚠️ Langfuse credentials missing. Tracing disabled.")

    async def _init_llm_service(self):
        """Initialize LLM models with fallback chain."""
        self._llm_service = LLMService()
    
    async def _init_reranker_service(self):
        """Initialize LLM models with fallback chain."""
        self._reranker_service = RerankerService()

    async def _init_storage_service(self):
        """Initialize StorageService."""
        self._storage_service = StorageService(rustfs_session=self.rustfs_session)

    async def _init_knowledge_service(self):
        """Initialize KnowledgeService."""
        self._knowledge_service = KnowledgeService(
            storage_service=self.storage_service,
            workspace_service=self.workspace_service
        )

    async def _init_agent_service(self):
        """Initialize AgentService."""
        self._agent_service = AgentService(
            graph=self.agent_graph,
            workspace_service=self.workspace_service,
            llm_service=self.llm_service,
            langfuse_client=self.langfuse_client
        )

    async def _init_workspace_service(self):
        self._workspace_service = WorkspaceService()

    async def _init_graph_ingestion_service(self):
        """Initialize GraphIngestionService."""
        self._graph_ingestion_service = GraphIngestionService(
            llm_service=self.llm_service,
            knowledge_graph=self.knowledge_graph,
            vector_store_solid=self.vector_store_solid,
            vector_store_volatile=self.vector_store_volatile
        )

    async def _init_embedding_model(self):
        """Initialize Gemini embedding model."""
        self._embedding_model = GeminiEmbeddingModel()

    async def _init_vector_store(self):
        """Initialize Qdrant using your Custom VectorStore Wrapper."""
        settings = get_settings()

        if settings.QDRANT_SOLID_KNOWLEDGE_COLLECTION_NAME is None:
            raise ValueError("Qdrant Collection Name is not configured")

        if settings.QDRANT_VOLATILE_KNOWLEDGE_COLLECTION_NAME is None:
            raise ValueError("Qdrant Volatile Knowledge Collection Name is not configured")
        
        qdrant_config_solid = VectorStore(
            collection_name=settings.QDRANT_SOLID_KNOWLEDGE_COLLECTION_NAME,
            vector_size=settings.QDRANT_VECTOR_SIZE, # 768
            url=settings.QDRANT_URL,
            dense_embedding=self.embedding_model
        )

        qdrant_config_volatile = VectorStore(
            collection_name=settings.QDRANT_VOLATILE_KNOWLEDGE_COLLECTION_NAME,
            vector_size=settings.QDRANT_VECTOR_SIZE, # 768
            url=settings.QDRANT_URL,
            dense_embedding=self.embedding_model
        )

        self._vector_store_solid = qdrant_config_solid.get_vector_store()
        self._vector_store_volatile = qdrant_config_volatile.get_vector_store()

    async def _init_searx_wrapper(self):
        """Initialize SearXNG Wrapper."""
        settings = get_settings()

        if settings.SEARXNG_HOST is None:
            raise ValueError("SEARX_HOST is not configured")

        self._searx_wrapper = SearxSearchWrapper(
            searx_host=settings.SEARXNG_HOST.get_secret_value()
        )

    async def _init_document_processor(self):
        """Initialize DocumentProcessor with the shared vector store."""
        self._document_processor = DocumentProcessor(
            vector_store_solid=self.vector_store_solid,
        )

    async def _init_knowledge_graph(self):
        """Initialize Neo4j Knowledge Graph and refresh its schema."""
        settings = get_settings()

        # Assuming your Settings model has these variables defined
        if not settings.NEO4J_URI or not settings.NEO4J_USERNAME or not settings.NEO4J_PASSWORD:
            logger.warning("Neo4j credentials not fully configured. Knowledge Graph will remain None.")
            return

        try:
            # Note: Neo4jGraph initialization is synchronous, 
            # but it is safe to run here during app startup.
            self._knowledge_graph = Neo4jGraph(
                url=settings.NEO4J_URI,
                username=settings.NEO4J_USERNAME,
                password=settings.NEO4J_PASSWORD.get_secret_value(),
                database="neo4j"        # "neo4j"
            )
            
            # Extract the schema immediately so it's cached in memory
            self._knowledge_graph.refresh_schema()
            logger.info("✅ Neo4j Knowledge Graph initialized and schema cached.")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {str(e)}")
            raise e

    async def _init_agent_graph(self):
        # Register instance-specific tools that have dependencies
        self._graph_rag_tool = make_graph_rag_tool(
            self.vector_store_solid,
            self.vector_store_volatile,
            self.knowledge_graph,
            self.llm_service
        )

        register_agent_tool(self._graph_rag_tool)
        
        # Register dynamic tools (like NCBI)
        # for t in self.ncbi_tools:
        #     register_agent_tool(t)

        self._agent_graph = await build_super_agent_graph(
            llm_service=self.llm_service,
            reranker_service=self.reranker_service,
            # graph_ingestion_service=self.graph_ingestion_service,
            vector_store_solid=self.vector_store_solid,
            vector_store_volatile=self.vector_store_volatile,
            searx_wrapper=self.searx_search,
            document_processor=self.document_processor, 
            available_tools=get_agent_tools()
        )

    async def _init_rustfs_session(self):
        """Initialize RustFS session (S3 compatible)"""
        self._rustfs_session = rustfs_session

    # async def _init_ncbi_tools(self):
    #     """Initialize dynamic tools from NCBI OpenAPI spec."""
    #     settings = get_settings()
    #     api_key = settings.ncbi_api_key.get_secret_value() if settings.ncbi_api_key else None
        
    #     self._ncbi_tools = build_openapi_tools(
    #         llm=self.llm_service.get_primary_model(),
    #         openapi_yaml_path=settings.ncbi_openapi_yaml_path,
    #         api_key=api_key
    #     )
    

    # --- Public accessors ---
    @property
    def langfuse_client(self) -> Langfuse:
        assert self._langfuse_client is not None, "Container not initialized (Langfuse Client missing)"
        return self._langfuse_client
    
    @property
    def llm_service(self) -> LLMService:
        assert self._llm_service, "Container not initialized (LLMService missing)"
        return self._llm_service
    
    @property
    def reranker_service(self) -> RerankerService:
        assert self._reranker_service, "Container not initialized (rerankerService missing)"
        return self._reranker_service
    
    @property
    def agent_service(self) -> AgentService:
        assert self._agent_service, "Container not initialized (AgentService missing)"
        return self._agent_service
    
    @property
    def knowledge_service(self) -> KnowledgeService:
        assert self._knowledge_service, "Container not initialized (KnowledgeService missing)"
        return self._knowledge_service
    
    @property
    def storage_service(self) -> StorageService:
        assert self._storage_service, "Container not initialized (StorageService missing)"
        return self._storage_service
    
    @property
    def workspace_service(self) -> WorkspaceService:
        assert self._workspace_service, "Container not initialized (WorkspaceService missing)"
        return self._workspace_service

    @property
    def graph_ingestion_service(self) -> GraphIngestionService:
        assert self._graph_ingestion_service, "Container not initialized (GraphIngestionService missing)"
        return self._graph_ingestion_service

    @property
    def embedding_model(self) -> GeminiEmbeddingModel:
        assert self._embedding_model, "Container not initialized (Embedding Model missing)"
        return self._embedding_model

    @property
    def vector_store_solid(self) -> QdrantVectorStore:
        assert self._vector_store_solid, "Container not initialized (QdrantVectorStoreSolid missing)"
        return self._vector_store_solid
    
    @property
    def vector_store_volatile(self) -> QdrantVectorStore:
        assert self._vector_store_volatile, "Container not initialized (QdrantVectorStoreVolatile missing)"
        return self._vector_store_volatile

    @property
    def document_processor(self) -> DocumentProcessor:
        assert self._document_processor, "Container not initialized (DocumentProcessor missing)"
        return self._document_processor
    
    @property
    def searx_search(self) -> SearxSearchWrapper:
        assert self._searx_wrapper, "Container not initialized (SearxSearch missing)"
        return self._searx_wrapper
    
    @property
    def knowledge_graph(self) -> Neo4jGraph:
        assert self._knowledge_graph, "Container not initialized (Knowledge Graph missing)"
        return self._knowledge_graph
    
    @property
    def agent_graph(self) -> CompiledStateGraph:
        assert self._agent_graph, "Container not initialized (Agent Graph missing)"
        return self._agent_graph

    @property
    def rustfs_session(self) -> aioboto3.Session:
        assert self._rustfs_session, "Container not initialized (RustFSClient missing)"
        return self._rustfs_session
    
    # @property
    # def ncbi_tools(self) -> List[BaseTool]:
    #     return self._ncbi_tools

# Singleton instance
_container = AppContainer()

def get_container() -> AppContainer:
    return _container
