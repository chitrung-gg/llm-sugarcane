from typing import Any, List

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
from pydantic import PrivateAttr

from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter


class MarkdownDocumentSplitter(AbstractDocumentSplitter):
    _headers = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    _splitter: Any = PrivateAttr()
    
    def model_post_init(self, __context: Any) -> None:
        self._splitter = MarkdownHeaderTextSplitter(self._headers)
    
    def process(self, file_path: str) -> List[Document]:
        text = self._read_text(file_path)
        return self._splitter.split_text(text)