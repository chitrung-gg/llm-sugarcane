import re
import os
from typing import Any, List

from langchain_core.documents import Document
from langchain_docling.loader import DoclingLoader, ExportType
from loguru import logger
from pydantic import PrivateAttr
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.pipeline_options import PdfPipelineOptions
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

from app.configs.settings.settings import get_settings
from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter
from app.utils.document.document_splitter_registry import DocumentSplitterRegistry

@DocumentSplitterRegistry.register(
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", 
    ".html", ".epub", ".msg", ".eml", ".rtf", ".odt", ".md", 
    ".tex", ".csv", ".png", ".jpeg"
)
class DoclingGenericSplitter(AbstractDocumentSplitter):

    # Issue 4: Prevent rebuilding the converter on every call
    _converter: Any = PrivateAttr(default=None)

    def process(self, file_path: str) -> List[Document]:
        raw_docs = self._load(file_path)
        
        full_content = self._clean(raw_docs)
        
        chunks = self._split(full_content)
        
        final_docs = self._inject_metadata(chunks, raw_docs, file_path)

        logger.info(f"Successfully chunked {os.path.basename(file_path)} into {len(final_docs)} segments.")
        return final_docs

    def _get_converter(self) -> DocumentConverter:
        """Lazily initializes and caches the DocumentConverter."""
        if self._converter is not None:
            return self._converter

        pdf_pipeline = PdfPipelineOptions()
        pdf_pipeline.do_ocr = False  
        pdf_pipeline.do_table_structure = True  
        pdf_pipeline.do_formula_enrichment = True
        pdf_pipeline.do_chart_extraction = True
        pdf_pipeline.do_code_enrichment = True

        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    backend=PyPdfiumDocumentBackend,
                    pipeline_options=pdf_pipeline
                )
            }
        )
        return self._converter

    def _load(self, file_path: str) -> List[Document]:
        """Handles document loading and markdown conversion."""
        logger.debug(f"Loading document: {os.path.basename(file_path)}")
        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.MARKDOWN,
            converter=self._get_converter()
        )
        
        raw_docs = loader.load()
        if not raw_docs:
            logger.warning(f"No text extracted from {file_path}.")
            
        return raw_docs

    def _clean(self, raw_docs: List[Document]) -> str:
        """Joins pages, strips artifacts, and removes references."""
        if not raw_docs:
            return ""

        # Issue 1: Join all pages instead of dropping everything past raw_docs[0]
        content = "\n\n".join([doc.page_content for doc in raw_docs if doc.page_content])

        # Issue 10: Strip standalone page numbers and basic running headers
        content = re.sub(r'^\s*\d+\s*$', '', content, flags=re.MULTILINE)

        # Issue 8: Robust Regex reference stripping 
        # Catches 'References', 'Bibliography', 'Literature Cited' even with markdown headers
        parts = re.split(r'\n#{1,3}\s*(?:References|Bibliography|Literature Cited|Tài liệu tham khảo)\b', content, flags=re.IGNORECASE)
        
        if len(parts) > 1:
            logger.debug("Successfully stripped references section via Regex.")
        
        return parts[0].strip()

    def _split(self, content: str) -> List[Document]:
        """Handles semantic and recursive chunking."""
        if not content:
            return []

        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on, 
            strip_headers=False
        )
        md_header_splits = markdown_splitter.split_text(content)

        # Issue 9: Protect Markdown tables by prioritizing "\n|" as a separator
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            separators=["\n\n", "\n|", "\n", ".", "!", "?", " ", ""]
        )
        
        return text_splitter.split_documents(md_header_splits)

    def _inject_metadata(self, chunks: List[Document], raw_docs: List[Document], file_path: str) -> List[Document]:
        """Merges base metadata with chunk-specific headers and RAG analytics."""
        if not chunks or not raw_docs:
            return chunks

        base_meta = raw_docs[0].metadata
        total_chunks = len(chunks)
        source_file = base_meta.get("source", os.path.basename(file_path))

        for i, doc in enumerate(chunks):
            # Issue 2 & 12: Base meta loaded first, doc meta (markdown headers) updates over it
            merged_meta = base_meta.copy()
            merged_meta.update(doc.metadata)

            # Issue 11: Add chunk analytics for RAG precision
            merged_meta["chunk_index"] = i
            merged_meta["total_chunks"] = total_chunks
            merged_meta["source_file"] = source_file
            merged_meta["chunk_type"] = "raw_literature"

            doc.metadata = merged_meta

        return chunks