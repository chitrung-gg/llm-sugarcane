import os
from typing import List

from langchain_core.documents import Document
from loguru import logger

from app.utils.document.abstract_document_splitter import AbstractDocumentSplitter
from app.utils.document.document_splitter_registry import DocumentSplitterRegistry

@DocumentSplitterRegistry.register(".collinearity")
class CollinearityDocumentSplitter(AbstractDocumentSplitter):
    def process(self, file_path: str) -> List[Document]:
        logger.debug(
            "Using Custom Bioinformatics Parser for {file_path}",
            file_path=file_path
        )
        
        docs = []
        current_block = []
        alignment_header = "Unknown Alignment"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines or standard parameter comments
                    if not line or line.startswith("# Parameters"):
                        continue
                        
                    # When we hit a new Alignment Block header
                    if line.startswith("## Alignment"):
                        # Save the previous block as a LangChain Document before starting the new one
                        if current_block:
                            docs.append(
                                Document(
                                    page_content="\n".join(current_block),
                                    metadata={
                                        "source": os.path.basename(file_path),
                                        "type": "synteny_block",
                                        "alignment_info": alignment_header
                                    }
                                )
                            )
                            
                        # Reset for the new block
                        alignment_header = line
                        current_block = [line]
                        
                    else:
                        # This is a gene pair row (e.g., "1-  1: geneA  geneB  e_value")
                        current_block.append(line)
                        
            # Don't forget to save the very last block in the file!
            if current_block:
                docs.append(
                    Document(
                        page_content="\n".join(current_block),
                        metadata={
                            "source": os.path.basename(file_path),
                            "type": "synteny_block",
                            "alignment_info": alignment_header
                        }
                    )
                )
                
            logger.debug(
                "✅ Successfully extracted {len_docs} synteny blocks.",
                len_docs = len(docs)
            )
            return docs
            
        except Exception as e:
            logger.exception(
                "❌ Failed to parse .collinearity file: {e}",
                e=e
            )
            raise ValueError(f"Could not read collinearity file: {e}")
        