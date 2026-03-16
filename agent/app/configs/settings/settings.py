from functools import lru_cache
import os

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
    gemini_llm_model: str = "gemini-3-flash-preview"   # gemini-2.5-flash
    gemini_embedding_model: str = "gemini-embedding-2-preview"  # gemini-embedding-001
    gemini_max_input_token: int = 200000

    # --- Qdrant ---
    qdrant_url: str = Field(default="localhost:6334", validation_alias="QDRANT_URL")
    qdrant_api_key: SecretStr | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(
        default="sugarcane_docs",
        validation_alias="QDRANT_COLLECTION_NAME"
    )
    qdrant_vector_size: int = 3072   # 768 to save storage
    qdrant_prefer_grpc: bool = True
    rag_score_threshold: float = 0.70

    # --- InMemory Store ---
    retriever_top_k: int = 3

    # --- SearxNG ---
    searx_host: SecretStr | None = Field(default=None, validation_alias="SEARXNG_HOST")  

    # --- LLM Service ---
    llm_max_retries: int = 3

    # --- Log ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # --- Langchain Docling ---
    docling_allow_external_plugins: str = Field(default="0", validation_alias="DOCLING_ALLOW_EXTERNAL_PLUGINS")
    
    # --- HuggingFaceTokenizer for DocumentProcessor ---
    hugging_face_tokenizer: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", validation_alias="HUGGING_FACE_TOKENIZER")


    # --- App ---
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = False


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached Settings singleton. It is a static class, then we can cache
    """
    return Settings()