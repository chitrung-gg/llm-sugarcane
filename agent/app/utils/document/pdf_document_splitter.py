# from typing import Any, List

# from langchain_core.documents import Document
# from langchain_community.document_loaders import PyPDFLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from pydantic import PrivateAttr

# from app.utils.document.document_splitter_registry import DocumentSplitterRegistry
# from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter

# @DocumentSplitterRegistry.register(".pdf")
# class PDFDocumentSplitter(AbstractDocumentSplitter):
#     chunk_size: int = 100
#     chunk_overlap: int = 0

#     _splitter: Any = PrivateAttr()
#     def model_post_init(self, __context: Any) -> None:
#         self._splitter = RecursiveCharacterTextSplitter(
#             chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
#         )
    
#     def process(self, file_path: str) -> List[Document]:
#         loader = PyPDFLoader(file_path)
#         docs = loader.load()
#         return self._splitter.split_documents(docs)
    