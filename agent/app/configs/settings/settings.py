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
    PRIMARY_GOOGLE_API_KEY: SecretStr | None = Field(
        default=None, 
        validation_alias="PRIMARY_GOOGLE_API_KEY"
    )
    SECONDARY_GOOGLE_API_KEY: SecretStr | None = Field(
        default=None, 
        validation_alias="SECONDARY_GOOGLE_API_KEY"
    )
    TERTIARY_GOOGLE_API_KEY: SecretStr | None = Field(
        default=None, 
        validation_alias="TERTIARY_GOOGLE_API_KEY"
    )
    QUATERNARY_GOOGLE_API_KEY: SecretStr | None = Field(
        default=None, 
        validation_alias="QUATERNARY_GOOGLE_API_KEY"
    )
    QUINARY_GOOGLE_API_KEY: SecretStr | None = Field(
        default=None, 
        validation_alias="QUINARY_GOOGLE_API_KEY"
    )
    EMBEDDING_GOOGLE_API_KEY: SecretStr | None = Field(
        default=None, 
        validation_alias="EMBEDDING_GOOGLE_API_KEY"
    )

    # GEMINI_PRIMARY_MODEL: str = Field(
    #     default="gemma-4-31b-it", 
    #     validation_alias="GEMINI_PRIMARY_MODEL"
    # )
    GEMINI_PRIMARY_MODEL: str = Field(
        default="gemini-3-flash-preview",           # "gemini-3-flash-preview"
        validation_alias="GEMINI_PRIMARY_MODEL"
    )
    # GEMINI_SECONDARY_MODEL: str = Field(
    #     default="gemini-3.1-flash-lite-preview", 
    #     validation_alias="GEMINI_SECONDARY_MODEL"
    # )
    GEMINI_SECONDARY_MODEL: str = Field(
        default="gemini-3.1-flash-lite",             # "gemini-2.5-flash"
        validation_alias="GEMINI_SECONDARY_MODEL"
    )
    GEMINI_TERTIARY_MODEL: str = Field(
        default="gemini-2.5-flash-lite", 
        validation_alias="GEMINI_TERTIARY_MODEL"
    )
    GEMINI_QUATERNARY_MODEL: str = Field(
        default="gemini-3.1-flash-lite", 
        validation_alias="GEMINI_QUATERNARY_MODEL"
    )
    GEMINI_QUINARY_MODEL: str = Field(
        default="gemma-4-26b-a4b-it", 
        validation_alias="GEMINI_QUINARY_MODEL"
    )

    GEMINI_EMBEDDING_MODEL: str = Field(
        default="gemini-embedding-2",   # "gemini-embedding-2":"gemini-embedding-001"
        validation_alias="GEMINI_EMBEDDING_MODEL"
    ) 
    GEMINI_MAX_INPUT_TOKEN: int = 200000

    # --- Langfuse ---
    LANGFUSE_SECRET_KEY: SecretStr | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
    LANGFUSE_PUBLIC_KEY: SecretStr | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    LANGFUSE_BASE_URL: str = Field(default="https://cloud.langfuse.com", validation_alias="LANGFUSE_BASE_URL")
    
    # --- Qdrant ---
    QDRANT_URL: str = Field(default="localhost:6334", validation_alias="QDRANT_URL")
    QDRANT_API_KEY: SecretStr | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    QDRANT_SOLID_KNOWLEDGE_COLLECTION_NAME: str = Field(
        default="sugarcane_docs_new",       # "sugarcane_docs_new"
        validation_alias="QDRANT_SOLID_KNOWLEDGE_COLLECTION_NAME"
    )
    QDRANT_VOLATILE_KNOWLEDGE_COLLECTION_NAME: str = Field(
        default="sugarcane_external_context_new",
        validation_alias="QDRANT_VOLATILE_KNOWLEDGE_COLLECTION_NAME"
    )
    KNOWLEDGE_GRAPH_SCORE_THRESHOLD: float = 0.5

    QDRANT_VECTOR_SIZE: int = 3072   # 768 to save storage
    QDRANT_PREFER_GRPC: bool = True

    QDRANT_SOLID_TOP_K: int = 20
    QDRANT_VOLATILE_TOP_K: int = 10
    QDRANT_FINAL_TOP_K: int = 2
    QDRANT_MAX_QUERY_LENGTH: int = 200

    QDRANT_BATCH_SIZE: int = 100

    # --- Neo4j ---
    NEO4J_URI: str = Field(
        default="neo4j://localhost:7687",
        validation_alias="NEO4J_URI"
    )
    NEO4J_USERNAME: str = Field(
        default="neo4j",
        validation_alias="NEO4J_USERNAME"
    )
    NEO4J_PASSWORD: SecretStr = Field(
        default=SecretStr("neo4j"), 
        validation_alias="NEO4J_PASSWORD"
    )

    # --- Genome Postgres ---
    GENOME_POSTGRES_URL: str = Field(
        default="postgresql://genome:genome@localhost:5432/sugarcane",
        validation_alias="GENOME_POSTGRES_URL"
    )

    # --- LangGraph's Postgres Checkpointer ---
    LANGGRAPH_POSTGRES_URL: str = Field(
        default="postgresql://langgraph:langgraph@localhost:5432/sugarcane",
        validation_alias="LANGGRAPH_POSTGRES_URL"
    )

    # --- User Data Postgres ---
    USERDATA_POSTGRES_URL: str = Field(
        default="postgresql://userdata:userdata@localhost:5432/sugarcane",
        validation_alias="USERDATA_POSTGRES_URL"
    )

    # --- KnowledgeGraph's Postgres ---
    KNOWLEDGEGRAPH_POSTGRES_URL: str = Field(
        default="postgresql://knowledge:knowledge@localhost:5432/sugarcane",
        validation_alias="KNOWLEDGEGRAPH_POSTGRES_URL"
    )

    # --- RabbitMQ ---
    KNOWLEDGEGRAPH_RABBITMQ_URL: str = Field(
        default="amqp://rabbitmq:rabbitmq@localhost:5672/llm-ingest-knowledgegraph",
        validation_alias="KNOWLEDGEGRAPH_RABBITMQ_URL"
    )

    # --- SearxNG ---
    SEARXNG_HOST: SecretStr | None = Field(default=None, validation_alias="SEARXNG_HOST")  

    # --- LLM Service ---
    LLM_MAX_RETRIES: int = 5
    LLM_TIMEOUT: float = 75.0

    # --- Log ---
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # --- Langchain Docling ---
    DOCLING_ALLOW_EXTERNAL_PLUGINS: str = Field(default="1", validation_alias="DOCLING_ALLOW_EXTERNAL_PLUGINS")

    # --- RustFS ---
    RUSTFS_ENDPOINT_URL: str = Field(
        default="http://localhost:9000",
        validation_alias="RUSTFS_ENDPOINT_URL"
    )
    RUSTFS_ACCESS_KEY_ID: str = Field(
        default="rustfs",
        validation_alias="RUSTFS_ACCESS_KEY_ID"
    )
    RUSTFS_SECRET_ACCESS_KEY: str = Field(
        default="rustfs",
        validation_alias="RUSTFS_SECRET_ACCESS_KEY"
    )
    RUSTFS_REGION_NAME: str = Field(
        default="ap-southeast-1",
        validation_alias="RUSTFS_REGION_NAME"
    )
    RUSTFS_USERS_BUCKET: str = Field(
        default="users-bucket",
        validation_alias="RUSTFS_USERS_BUCKET"
    )
    

    # --- Genome Tool ---
    GENOME_BACKEND_API_URL: str = Field(
        default="http://localhost:8001", validation_alias="GENOME_BACKEND_API_URL"
    )

    # --- NCBI Tool ---
    # NCBI_OPENAPI_YAML_PATH: str = Field(
    #     default="resources/ncbi_dataset_openapi_truncated.yaml", 
    #     validation_alias="NCBI_OPENAPI_YAML_PATH"
    # )
    NCBI_AGENT_NAME: SecretStr | None = Field(
        default=None, 
        validation_alias="NCBI_AGENT_NAME"
    )
    NCBI_EMAIL: SecretStr | None = Field(
        default=None, 
        validation_alias="NCBI_EMAIL"
    )
    NCBI_API_KEY: SecretStr | None = Field(
        default=None, 
        validation_alias="NCBI_API_KEY"
    )

    # Airflow
    AIRFLOW_BASE_URL: str = Field(
        default="http://localhost:8080",
        validation_alias="AIRFLOW_BASE_URL"
    )
    AIRFLOW_API_AUTH_USERNAME: str = Field(
        default="airflow",
        validation_alias="AIRFLOW_API_AUTH_USERNAME"
    )
    AIRFLOW_API_AUTH_PASSWORD: SecretStr | None = Field(
        default=None,
        validation_alias="AIRFLOW_API_AUTH_PASSWORD"
    )

    # Pipelines
    INGESTION_BATCH_SIZE: int = 10
    INGESTION_DELAY_BETWEEN_BATCHES: int = 30

    # Graph Nodes
    INNER_AGENT_MAX_ITERATION: int = 1

    ROUTER_MAX_RAG_RESULTS_LENGTH: int = 1000
    ROUTER_MAX_WEB_RESULTS_LENGTH: int = 1000
    ROUTER_MAX_TOOL_RESULTS_LENGTH: int = 3000

    RAG_INMEMORY_RETRIEVER_TOP_K: int = 3

    TOOLS_MAX_TOOL_OUTPUT_LENGTH: int = 20000

    WEB_SEARCH_TIMEOUT_SEC: float = 15.0
    WEB_SEARCH_MAX_QUERY_LENGTH: int = 200
    WEB_SEARCH_NUM_RESULTS: int = 10
    WEB_SEARCH_SCORE_THRESHOLD: float = 0.5

    SUMMARIZER_SUMMARY_TRIGGER_THRESHOLD: int = 10
    SUMMARIZER_SUMMARY_KEEP_LAST_N: int = 2
    SUMMARIZER_SUMMARY_TIMEOUT_SEC: float = 20.0

    SYNTHESIZER_TIMEOUT_SEC: float = 45.0


    # --- App ---
    APP_ENV: str = Field(default="development", validation_alias="APP_ENV")


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached Settings singleton.
    """
    return Settings()