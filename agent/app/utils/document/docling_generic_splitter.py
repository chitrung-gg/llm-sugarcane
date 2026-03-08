from typing import Any, List

from langchain_core.documents import Document
from langchain_docling.loader import DoclingLoader, ExportType
from loguru import logger
from pydantic import PrivateAttr
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter
from app.utils.document.document_splitter_registry import DocumentSplitterRegistry


@DocumentSplitterRegistry.register(
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", 
    ".html", ".epub", ".msg", ".eml", ".rtf", ".odt"
)
class DoclingGenericSplitter(AbstractDocumentSplitter):
    _splitter: Any = PrivateAttr(default=None)

    def process(self, file_path: str) -> List[Document]:
        logger.debug(f"Using Docling to parse {file_path}")

        pipeline_options = PdfPipelineOptions()
        pipeline_options.allow_external_plugins = True
        # Disable OCR if needed to speed things up
        # pipeline_options.do_ocr = False 

        # Build the converter
        doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # Explicitly set the export type to DOC_CHUNKS!
        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.DOC_CHUNKS,
            converter=doc_converter
        )
        
        docs = loader.load()

        logger.debug(f"Successfully chunked document into {len(docs)} segments.")
        return docs