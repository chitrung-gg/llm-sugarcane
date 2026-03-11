from .document_splitter_registry import DocumentSplitterRegistry
from .abstract_document_splitter import AbstractDocumentSplitter

# Import all splitters to trigger their registration decorators
# from .unstructured_generic_splitter import UnstructuredGenericSplitter
from .docling_generic_splitter import DoclingGenericSplitter
from .collinearity_document_splitter import CollinearityDocumentSplitter
# Add your PDF and Markdown splitters here tool