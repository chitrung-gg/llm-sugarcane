from typing import Any

from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from pydantic import BaseModel, PrivateAttr
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, SparseVectorParams

from app.core.embeddings.gemini_embeddings_model import GeminiEmbeddingModel


class VectorStore(BaseModel):
    collection_name: str
    vector_size: int = 3072     # Default: 3072, use 768 to save storage space
    distance: Distance = Distance.COSINE

    _sparse_embedding: FastEmbedSparse = PrivateAttr()
    dense_embedding: GeminiEmbeddingModel
    _client: QdrantClient = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        self._sparse_embedding = FastEmbedSparse(model_name="Qdrant/bm25")

        self._client = QdrantClient(path="/tmp/langchain_qdrant")

        if not self._client.collection_exists(self.collection_name):
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(size=self.vector_size, distance=self.distance)
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
                }
            )
            print(f"Created collection'{self.collection_name}' successfully")


    def get_vector_store(self) -> QdrantVectorStore:
        """Return VectorStore instance"""
        return QdrantVectorStore(
            client=self._client,
            collection_name=self.collection_name,
            embedding=self.dense_embedding.get_embeddings(),
            sparse_embedding=self._sparse_embedding,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse"
        )
    
