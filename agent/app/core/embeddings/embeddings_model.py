import os

from pydantic import BaseModel

"""
    Abstract the EmbeddingModel from different vendors
    Embedding Model is used for converting text into compact numerical vectors to map semantic meaning
"""
class EmbeddingModel(BaseModel):
    def __init__(self, embedding_api_key):
        self.embedding_api_key = embedding_api_key