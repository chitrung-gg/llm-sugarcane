from pathlib import Path
from typing import Any, Dict, List

from langchain_qdrant import QdrantVectorStore
from pydantic import BaseModel, ConfigDict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.utils.document.document_splitter_registry import DocumentSplitterRegistry
class DocumentProcessor(BaseModel):
    """
    Processes uploaded files into vector store chunks.
    Delegates parsing/chunking to the appropriate registered splitter
    based on file extension — no manual splitter selection needed.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    vector_store: QdrantVectorStore

    def process_and_store(self, file_path: str) -> List[str]:
        print(f"Analyzing file: {file_path}")
        
        # Get correct document splitter for each file type
        splitter = DocumentSplitterRegistry.get_splitter(file_path)
        
        chunks = splitter.process(file_path)
        
        if not chunks: 
            print("Cannot get content of file.")
            return []

        print(f"-> Cutted into {len(chunks)} chunks. Saving into Qdrant...")
        
        # Add to Vector Database
        inserted_ids = self.vector_store.add_documents(chunks)
        print(f"Successfully saved {len(inserted_ids)} chunks!")
        
        return inserted_ids
        
    def process_and_get_chunks(self, file_path: str) -> List[Document]:
        """
        Parses and chunks a file without storing — useful for injecting
        file content directly into the agent's context window (input_processor node).

        Args:
            file_path: Path to the uploaded file.

        Returns:
            List of LangChain Document chunks with metadata.
        """
        splitter = DocumentSplitterRegistry.get_splitter(file_path)
        return splitter.process(file_path)

