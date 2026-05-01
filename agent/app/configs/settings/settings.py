from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Loads all configuration from environment variables or .env file.
    Never instantiate this directly in modules — use get_settings() to get the cached singleton.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Gemini ---
    google_api_key: SecretStr | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    # gemini_primary_model: str = Field(
    #     default="gemma-4-31b-it", 
    #     validation_alias="GEMINI_PRIMARY_MODEL"
    # )
    gemini_primary_model: str = Field(
        default="gemini-3-flash-preview", 
        validation_alias="GEMINI_PRIMARY_MODEL"
    )
    # gemini_secondary_model: str = Field(
    #     default="gemini-3.1-flash-lite-preview", 
    #     validation_alias="GEMINI_SECONDARY_MODEL"
    # )
    gemini_secondary_model: str = Field(
        default="gemini-2.5-flash", 
        validation_alias="GEMINI_SECONDARY_MODEL"
    )
    gemini_tertiary_model: str = Field(
        default="gemini-2.5-flash-lite", 
        validation_alias="GEMINI_TERTIARY_MODEL"
    )
    gemini_quaternary_model: str = Field(
        default="gemma-4-26b-a4b-it", 
        validation_alias="GEMINI_QUATERNARY_MODEL"
    )

    gemini_embedding_model: str = Field(
        default="gemini-embedding-2-preview",   # "gemini-embedding-001"
        validation_alias="GEMINI_PRIMARY_EMBEDDING_MODEL"
    ) 
    gemini_max_input_token: int = 200000

    # --- Langfuse ---
    langfuse_secret_key: SecretStr | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_public_key: SecretStr | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_base_url: str = Field(default="https://cloud.langfuse.com", validation_alias="LANGFUSE_BASE_URL")
    
    # --- Qdrant ---
    qdrant_url: str = Field(default="localhost:6334", validation_alias="QDRANT_URL")
    qdrant_api_key: SecretStr | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_solid_knowledge_collection_name: str = Field(
        default="sugarcane_docs",
        validation_alias="QDRANT_SOLID_KNOWLEDGE_COLLECTION_NAME"
    )
    qdrant_volatile_knowledge_collection_name: str = Field(
        default="sugarcane_external_context",
        validation_alias="QDRANT_VOLATILE_KNOWLEDGE_COLLECTION_NAME"
    )

    qdrant_vector_size: int = 3072   # 768 to save storage
    qdrant_prefer_grpc: bool = True
    rag_score_threshold: float = 0.70

    # --- Neo4j ---
    neo4j_uri: str = Field(
        default="neo4j://localhost:7687",
        validation_alias="NEO4J_URI"
    )
    neo4j_username: str = Field(
        default="neo4j",
        validation_alias="NEO4J_USERNAME"
    )
    neo4j_password: SecretStr = Field(
        default=SecretStr("neo4j"), 
        validation_alias="NEO4J_PASSWORD"
    )

    # --- InMemory Store ---
    inmemory_retriever_top_k: int = 3

    # --- Genome Postgres ---
    genome_postgres_url: str = Field(
        default="postgresql://genome:genome@localhost:5432/sugarcane",
        validation_alias="GENOME_POSTGRES_URL"
    )

    # --- LangGraph's Postgres Checkpointer ---
    langgraph_postgres_url: str = Field(
        default="postgresql://langgraph:langgraph@localhost:5432/sugarcane",
        validation_alias="LANGGRAPH_POSTGRES_URL"
    )

    # --- User Data Postgres ---
    userdata_postgres_url: str = Field(
        default="postgresql://userdata:userdata@localhost:5432/sugarcane",
        validation_alias="USERDATA_POSTGRES_URL"
    )

    # --- KnowledgeGraph's Postgres ---
    knowledgegraph_postgres_url: str = Field(
        default="postgresql://knowledge:knowledge@localhost:5432/sugarcane",
        validation_alias="KNOWLEDGEGRAPH_POSTGRES_URL"
    )

    # --- RabbitMQ ---
    knowledgegraph_rabbitmq_url: str = Field(
        default="amqp://rabbitmq:rabbitmq@localhost:5672/llm-ingest-knowledgegraph",
        validation_alias="KNOWLEDGEGRAPH_RABBITMQ_URL"
    )

    # --- SearxNG ---
    searx_host: SecretStr | None = Field(default=None, validation_alias="SEARXNG_HOST")  

    # --- LLM Service ---
    llm_max_retries: int = 3
    llm_timeout: int = 20

    # --- Log ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # --- Langchain Docling ---
    docling_allow_external_plugins: str = Field(default="0", validation_alias="DOCLING_ALLOW_EXTERNAL_PLUGINS")
    
    # --- HuggingFaceTokenizer for DocumentProcessor ---
    hugging_face_tokenizer: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", validation_alias="HUGGING_FACE_TOKENIZER")

    # --- RustFS ---
    rustfs_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias="RUSTFS_ENDPOINT_URL"
    )
    rustfs_access_key_id: str = Field(
        default="rustfs",
        validation_alias="RUSTFS_ACCESS_KEY_ID"
    )
    rustfs_secret_access_key: str = Field(
        default="rustfs",
        validation_alias="RUSTFS_SECRET_ACCESS_KEY"
    )
    rustfs_region_name: str = Field(
        default="ap-southeast-1",
        validation_alias="RUSTFS_REGION_NAME"
    )
    rustfs_users_bucket: str = Field(
        default="users-bucket",
        validation_alias="RUSTFS_USERS_BUCKET"
    )
    

    # --- Genome Tool ---
    genome_backend_api_url: str = Field(
        default="http://localhost:8001", validation_alias="GENOME_BACKEND_API_URL"
    )

    # --- NCBI Tool ---
    # ncbi_openapi_yaml_path: str = Field(
    #     default="resources/ncbi_dataset_openapi_truncated.yaml", 
    #     validation_alias="NCBI_OPENAPI_YAML_PATH"
    # )
    ncbi_agent_name: SecretStr | None = Field(
        default=None, 
        validation_alias="NCBI_TOOL"
    )
    ncbi_email: SecretStr | None = Field(
        default=None, 
        validation_alias="NCBI_EMAIL"
    )
    ncbi_api_key: SecretStr | None = Field(
        default=None, 
        validation_alias="NCBI_API_KEY"
    )

    # --- App ---
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = False


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached Settings singleton. It is a static class, then we can cache
    """
    return Settings()