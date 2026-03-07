from typing import Any, List

from langchain_core.documents import Document
from langchain_unstructured import UnstructuredLoader
from loguru import logger
from pydantic import PrivateAttr

from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter
from app.utils.document.document_splitter_registry import DocumentSplitterRegistry

@DocumentSplitterRegistry.register(
    ".pdf",
    ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", 
    ".html", ".epub", ".msg", ".eml", ".rtf", ".odt"
)
class UnstructuredGenericSplitter(AbstractDocumentSplitter):
    _splitter: Any = PrivateAttr()

    def process(self, file_path: str) -> List[Document]:
        logger.debug(f"Using Unstructured to parse {file_path}...")

        # 'elements' mode keeps tables and text separate and clean
        loader = UnstructuredLoader(file_path, mode="elements")
        docs = loader.load()
        
        # Unstructured already chunks by element (paragraphs, tables, titles)
        # So you often don't even need a RecursiveCharacterTextSplitter here!
        return docs