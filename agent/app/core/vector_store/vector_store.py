from enum import StrEnum
import os
from typing import Any, List

from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Condition, Distance, VectorParams, SparseVectorParams
from langchain_core.embeddings import Embeddings

class VectorStoreType(StrEnum):
    SOLID = "solid"
    VOLATILE = "volatile"

class SparseEmbeddingWrapper:
    def __init__(self, sparse_embedding: FastEmbedSparse):
        self.sparse_embedding = sparse_embedding

    def embed_documents(self, texts: List[str]) -> List[Any]:
        from loguru import logger
        logger.debug(f"Embedding {len(texts)} documents with FastEmbed (Sparse)...")
        try:
            embeddings = self.sparse_embedding.embed_documents(texts)
            if len(embeddings) != len(texts):
                logger.error(f"Mismatched length (Sparse): {len(texts)} input, {len(embeddings)} output")
                logger.error(f"Batch content for mismatch: {texts}")
            return embeddings
        except Exception as e:
            logger.error(f"Sparse embedding failed for batch of {len(texts)}: {e}")
            logger.error(f"Batch content: {texts}")
            raise e

    def embed_query(self, text: str):
        return self.sparse_embedding.embed_query(text)

class VectorStore(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    collection_name: str
    vector_size: int = 3072     # Default: 3072, use 768 to save storage space
    distance: Distance = Distance.COSINE

    _sparse_embedding: Any = PrivateAttr()
    dense_embedding: Embeddings # Changed from GeminiEmbeddingModel to generic Embeddings
    _client: QdrantClient = PrivateAttr()

    url: str = Field(
        default_factory=lambda: os.getenv("QDRANT_URL") or "localhost:6334"
    )


    def model_post_init(self, __context: Any) -> None:
        sparse_engine = FastEmbedSparse(model_name="prithivida/Splade_PP_en_v1")
        self._sparse_embedding = SparseEmbeddingWrapper(sparse_engine)


        self._client = QdrantClient(url=self.url, prefer_grpc=True)

        if not self._client.collection_exists(self.collection_name):
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(size=self.vector_size, distance=self.distance)
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=True))
                }
            )
            print(f"Created collection'{self.collection_name}' successfully")


    def get_vector_store(self) -> QdrantVectorStore:
        """Return VectorStore instance"""
        return QdrantVectorStore(
            client=self._client,
            collection_name=self.collection_name,
            embedding=self.dense_embedding, # Use directly
            sparse_embedding=self._sparse_embedding,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse"
        )

def build_metadata_filter(metadata: dict, prefix: str = "metadata.") -> models.Filter:
    """
    Builds a validated Qdrant Filter object from a metadata dictionary.
    Supports single values (AND logic) and lists of values (OR logic).
    """
    must_conditions = []

    for key, value in metadata.items():
        actual_key = f"{prefix}{key}" if prefix else key
        
        # If the value is a list, we need a 'should' (OR) condition for this specific key
        if isinstance(value, list):
            should_conditions: List[Condition] = [
                models.FieldCondition(
                    key=actual_key,
                    match=models.MatchValue(value=str(v))
                ) for v in value
            ]
            # Wrap the OR conditions inside a nested Filter and add to the main MUST list
            must_conditions.append(models.Filter(should=should_conditions))
            
        # If it's a single value, just do standard 'must' (AND) matching
        else:
            must_conditions.append(
                models.FieldCondition(
                    key=actual_key,
                    match=models.MatchValue(value=str(value))
                )
            )
            
    return models.Filter(must=must_conditions)