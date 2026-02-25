from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document
from pydantic import BaseModel

class AbstractDocumentSplitter(ABC, BaseModel):
    @abstractmethod
    def process(self, file_path: str) -> List[Document]:
        """ Read the files and return chunks in LangChain's Document format """
        pass

    def _read_text(self, file_path: str) -> str:
        """ Utils for reading file """
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
