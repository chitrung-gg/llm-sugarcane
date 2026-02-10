import getpass
import os

from fastapi.logger import logger
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

if not os.getenv("PINECONE_API_KEY"):
    logger.log(level=1, msg="Unable to retrieve Pinecone API Key, please recheck")

pinecone_api_key = os.environ.get("PINECONE_API_KEY")
pc = Pinecone(api_key=pinecone_api_key)



index_name = "langchain-test-index"

if not pc.has_index(index_name):
    print("Index does not exists, creating ...")
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",            # Focus on vector direction rather than magnitude
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(index_name)
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001"                # best Gemini model for embeddings
)


vector_store = PineconeVectorStore(index=index, embedding=embeddings)