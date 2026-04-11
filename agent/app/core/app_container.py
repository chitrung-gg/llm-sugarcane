from functools import lru_cache
from typing import List

from langchain_neo4j import Neo4jGraph
from langchain_qdrant import QdrantVectorStore
from langchain_community.utilities.searx_search import SearxSearchWrapper
from langgraph.graph.state import CompiledStateGraph
from langchain_core.tools import BaseTool
from loguru import logger
from botocore.client import BaseClient

from app.services.agent.agent_service import AgentService
from app.core.tools.ncbi_eutils_tool import get_gene_metadata_by_symbol, search_literature_for_traits, search_ncbi_genome
from app.core.tools.openapi_tool import build_openapi_tools
from app.core.graph.graph import build_agent_graph
from app.configs.settings.settings import get_settings
from app.services.llm.llm_service import LLMService
from app.utils.document_processor import DocumentProcessor
from app.services.knowledge.graph_ingestion_service import GraphIngestionService

from app.core.embeddings.gemini_embeddings_model import GeminiEmbeddingModel
from app.core.vector_store.vector_store import VectorStore
from app.configs.storage.object_storage import rustfs_client
from app.core.tools.genome_tool import (
    design_polyploid_primer, get_gene_detail,
    get_genes_list, list_genome_files, run_blast, run_crispor,
    run_synteny_analysis, search_genes_full
)
from app.core.tools.graph_rag_tool import make_graph_rag_tool

class AppContainer:
    """Central dependency container."""

    def __init__(self):
        self._llm_service: LLMService | None = None
        self._agent_service: AgentService | None = None
        self._graph_ingestion_service: GraphIngestionService | None = None
        self._embedding_model: GeminiEmbeddingModel | None = None
        self._vector_store: QdrantVectorStore | None = None
        self._document_processor: DocumentProcessor | None = None
        self._searx_wrapper: SearxSearchWrapper | None = None
        self._knowledge_graph: Neo4jGraph | None = None
        self._agent_graph: CompiledStateGraph | None = None
        self._graph_rag_tool: BaseTool | None = None
        self._rustfs_client: BaseClient | None = None

    async def initialize(self):
        logger.info(" Initializing app container...")
        
        # 1. Base Services & APIs
        await self._init_llm_service() 
        await self._init_rustfs_client()
        await self._init_searx_wrapper()
        await self._init_ncbi_tools()
        
        # 2. Databases & Storage
        await self._init_embedding_model()
        await self._init_vector_store()
        await self._init_knowledge_graph()
        
        # 3. Middlewares & Processors (Depends on Storage)
        await self._init_document_processor()
        await self._init_graph_ingestion_service()
        
        # 4. The Graph (Depends on ALL of the above)
        await self._init_agent_graph()
        
        # 5. The Top-Level Service (Depends on the Graph)
        await self._init_agent_service() 
        
        logger.info(" App container ready.")

    async def _init_llm_service(self):
        """Initialize LLM models with fallback chain."""
        self._llm_service = LLMService()

    async def _init_agent_service(self):
        """Initialize LLM models with fallback chain."""
        self._agent_service = AgentService(
            graph=self.agent_graph,
            rustfs_client=self.rustfs_client,
            llm_service=self.llm_service
        )

    async def _init_graph_ingestion_service(self):
        """Initialize GraphIngestionService."""
        self._graph_ingestion_service = GraphIngestionService(
            llm_service=self.llm_service,
            knowledge_graph=self.knowledge_graph,
            vector_store=self.vector_store
        )

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

    async def _init_knowledge_graph(self):
        """Initialize Neo4j Knowledge Graph and refresh its schema."""
        settings = get_settings()

        # Assuming your Settings model has these variables defined
        if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
            logger.warning("Neo4j credentials not fully configured. Knowledge Graph will remain None.")
            return

        try:
            # Note: Neo4jGraph initialization is synchronous, 
            # but it is safe to run here during app startup.
            self._knowledge_graph = Neo4jGraph(
                url=settings.neo4j_uri,
                username=settings.neo4j_username,
                password=settings.neo4j_password.get_secret_value()
            )
            
            # Extract the schema immediately so it's cached in memory
            self._knowledge_graph.refresh_schema()
            logger.info("✅ Neo4j Knowledge Graph initialized and schema cached.")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {str(e)}")
            raise e

    async def _init_agent_graph(self):
        """
        Builds the LangGraph once during startup.

        Because each method return the name depends on the OpenAPI specs, and can be changed over time, so we should build the list dynamically
        """
        self._graph_rag_tool = make_graph_rag_tool(self.vector_store, self.knowledge_graph)

        static_tools = [
            list_genome_files, get_genes_list, search_genes_full,
            get_gene_detail, run_blast, run_synteny_analysis, 
            run_crispor, design_polyploid_primer, search_literature_for_traits, get_gene_metadata_by_symbol, search_ncbi_genome, self._graph_rag_tool
        ]        # Combine static and dynamic tools into a dictionary
        # all_tools = {tool.name: tool for tool in static_tools + self.ncbi_tools}
        all_tools = {tool.name: tool for tool in static_tools}

        self._agent_graph = await build_agent_graph(
            llm_service=self.llm_service,
            graph_ingestion_service=self.graph_ingestion_service,
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
    def agent_service(self) -> AgentService:
        assert self._agent_service, "Container not initialized (AgentService missing)"
        return self._agent_service
    
    @property
    def graph_ingestion_service(self) -> GraphIngestionService:
        assert self._graph_ingestion_service, "Container not initialized (GraphIngestionService missing)"
        return self._graph_ingestion_service

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
    def knowledge_graph(self) -> Neo4jGraph:
        assert self._knowledge_graph, "Container not initialized (Knowledge Graph missing)"
        return self._knowledge_graph
    
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