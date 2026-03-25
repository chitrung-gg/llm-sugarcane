from typing import Any, List

from langchain_core.documents import Document
from langchain_docling.loader import DoclingLoader, ExportType
from loguru import logger
from pydantic import PrivateAttr
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from transformers import AutoTokenizer


from app.configs.settings.settings import get_settings
from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter
from app.utils.document.document_splitter_registry import DocumentSplitterRegistry


@DocumentSplitterRegistry.register(
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", 
    ".html", ".epub", ".msg", ".eml", ".rtf", ".odt", ".md", 
    ".tex", ".csv", ".png", ".jpeg"
)
class DoclingGenericSplitter(AbstractDocumentSplitter):

    _splitter: Any = PrivateAttr(default=None)

    def process(self, file_path: str) -> List[Document]:
        settings = get_settings()
        logger.debug(f"Using Docling to parse {file_path}")

        pipeline_options = PdfPipelineOptions()
        pipeline_options.allow_external_plugins = True
        # Disable OCR if needed to speed things up
        pipeline_options.do_ocr = False 

        # Build the converter
        doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # Config HybridChunker
        # Use better embedding model as from the MTEB Leaderboard if resources allow
        tokenizer = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained(settings.hugging_face_tokenizer),
            max_tokens=500
        )


        # Explicitly set the export type to DOC_CHUNKS!
        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.DOC_CHUNKS,
            converter=doc_converter,
            chunker=HybridChunker(tokenizer=tokenizer)
        )
        
        docs = loader.load()

        logger.debug(f"Successfully chunked document into {len(docs)} segments.")
        return docs