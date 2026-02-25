from pathlib import Path
from typing import Any, Dict, List

from langchain_qdrant import QdrantVectorStore
from pydantic import BaseModel, ConfigDict
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.document.factory_document_splitter import FactoryDocumentSplitter
from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter

class DocumentProcessor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    vector_store: QdrantVectorStore

    def process_and_store(self, file_path: str) -> List[str]:
        print(f"📄 Đang phân tích file: {file_path}")
        
        # Get correct document splitter for each file type
        splitter = FactoryDocumentSplitter.get_splitter(file_path)
        
        chunks = splitter.process(file_path)
        
        if not chunks: 
            print("Cannot get content of file.")
            return []

        print(f"-> Cutted into {len(chunks)} chunks. Saving into Qdrant...")
        
        # Add to Vector Database
        inserted_ids = self.vector_store.add_documents(chunks)
        print(f"Successfully saved {len(inserted_ids)} chunks!")
        
        return inserted_ids
        


