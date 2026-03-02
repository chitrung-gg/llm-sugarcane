from pathlib import Path
from typing import Dict, Type

from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter


class DocumentSplitterRegistry:
    # Factory Method & Decorator Design Pattern
    _registry: Dict[str, AbstractDocumentSplitter] = {}

    @classmethod
    def register(cls, *extensions: str):
        """
        Decorator to auto-register a splitter class for one or more file extensions.

        Usage:
            @DocumentSplitterRegistry.register(".pdf", ".PDF")
            class PdfSplitter(AbstractDocumentSplitter): ...
        """
        def decorator(splitter_cls: Type[AbstractDocumentSplitter]):
            instance = splitter_cls()
            for ext in extensions:
                cls._registry[ext.lower()] = instance
            return splitter_cls
        return decorator
    
    @classmethod
    def get_splitter(cls, file_path: str) -> AbstractDocumentSplitter:
        """ Get correct document splitter utils for each file type """
        ext = Path(file_path).suffix.lower()
        splitter = cls._registry.get(ext)

        if not splitter:
            raise ValueError(
                f"No splitter registered for extension '{ext}'. "
                f"Registered types: {list(cls._registry.keys())}"
            )
        return splitter
    
    @classmethod
    def registered_extensions(cls) -> list[str]:
        """Returns all currently registered file extensions."""
        return list(cls._registry.keys())