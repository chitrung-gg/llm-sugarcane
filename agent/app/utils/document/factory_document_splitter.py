from pathlib import Path
from typing import Dict

from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter


class FactoryDocumentSplitter:
    _registry: Dict[str, AbstractDocumentSplitter] = {}

    @classmethod
    def register(cls, extension: str, splitter: AbstractDocumentSplitter):
        cls._registry[extension.lower()] = splitter
    
    @classmethod
    def get_splitter(cls, file_path: str) -> AbstractDocumentSplitter:
        """ Get correct document splitter utils for each file type """
        ext = Path(file_path).suffix.lower()
        splitter = cls._registry.get(ext)

        if not splitter:
            raise ValueError(f"System currently cannot process file type: {ext}")
        return splitter