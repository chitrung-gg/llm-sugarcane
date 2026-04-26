# from typing import Any, List, Literal

# from loguru import logger
# from pydantic import BaseModel, Field
# from langchain_core.messages import SystemMessage, HumanMessage

# from app.common.constants import GENOMIC_EXTENSIONS, KNOWLEDGE_EXTENSIONS, is_genomic_file, is_knowledge_file
# from app.services.llm.llm_service import LLMService

# # Keep these just to provide hints to the LLM prompt, not as hard rules.



# class FileClassification(BaseModel):
#     category: Literal["genomic", "knowledge", "sample_only", "reject"] = Field(
#         description="The routing category for the uploaded file."
#     )
#     reason: str = Field(
#         description="A short explanation of why this category was chosen based on user intent."
#     )

# async def classify_upload_with_llm(
#     filename: str, 
#     user_query: str,
#     file_snippet: str,
#     llm_service: LLMService,
#     callbacks: List[Any] | None = None
# ) -> Literal["genomic", "knowledge", "sample_only", "reject"]:
#     """
#     Uses a fast LLM to dynamically determine file routing based on user intent.
#     """
#     structured_llm = llm_service.get_structured_secondary_model(FileClassification)

#     # 1. Use native Python f-strings inside SystemMessage and HumanMessage
#     messages = [
#         SystemMessage(content="""
#             You are an intelligent file routing system for a Bioinformatics platform.
#             Look at the specific uploaded file name and the user's message, and determine how to handle it.

#             ROUTING RULES:
#             1. 'sample_only': Choose this if the user wants to EXPLAIN, INTERPRET, UNDERSTAND, or SUMMARIZE the format, headers, or columns of a data file.
#             2. 'genomic': Choose this if the user explicitly wants to run a HEAVY COMPUTATIONAL BACKEND TOOL (like BLAST, synteny, mapping) on this file.
#             3. 'knowledge': Choose this for human-readable documents (papers, notes) OR if the user wants you to directly read/translate a small text file.
#             4. 'reject': The file looks like malware (.exe, .sh) or the intent is completely unrelated to biology/system tasks.

#             CRITICAL EDGE CASES:
#             - EMPTY/VAGUE QUERIES: Rely heavily on the file extension. Route documents to 'knowledge' and genomic datasets to 'genomic'.
#             - INTENT OVER EXTENSION: If they upload a massive '.gff3' but just ask 'what do these columns mean?', route to 'sample_only'.
#         """),
#         HumanMessage(content=f"""
#             File being evaluated: {filename}
#             User Message: {user_query or '[NO MESSAGE PROVIDED]'}
            
#             --- Start of File Preview (First few lines) ---
#             {file_snippet if file_snippet else '[NO PREVIEW AVAILABLE]'}
#             --- End of File Preview ---
#         """)
#     ]

#     try:
#         # 2. Pass the message list directly to the structured LLM
#         raw_result = await structured_llm.ainvoke(
#             messages,
#             config={"callbacks": callbacks} if callbacks else None
#         )
#         result = FileClassification.model_validate(raw_result)
        
#         logger.info(f"[File Classifier] Routed '{filename}' to {result.category}. Reason: {result.reason}")
#         return result.category
        
#     except Exception as e:
#         logger.error(f"[File Classifier] LLM failed: {e}. Falling back to strict extension checking.")
#         return _fallback_classifier(filename, user_query)


# def _fallback_classifier(filename: str, user_query: str) -> Literal["genomic", "knowledge", "sample_only", "reject"]:
#     """Fallback in case the LLM API fails."""
#     query_words = set(user_query.lower().split())
    
#     interpret_keywords = {"explain", "interpret", "what", "how", "structure", "format", "columns"}
#     if query_words & interpret_keywords:
#         return "sample_only"

#     if is_genomic_file(filename):
#         return "genomic"
#     if is_knowledge_file(filename):
#         return "knowledge"
        
#     return "reject"

from pathlib import Path

from app.common.constants import COMPRESSED_SUFFIXES, GENOMIC_EXTENSIONS, KNOWLEDGE_EXTENSIONS


def extract_full_extension(filename: str) -> str:
    """
    Safely extracts double-extensions like '.fasta.gz' or '.gff3.gz'.
    Otherwise, returns the single extension like '.pdf'.
    """
    path = Path(filename)
    suffixes = path.suffixes
    
    if not suffixes:
        return ""
        
    # If the last suffix is a compression format and there is a base format before it
    if len(suffixes) >= 2 and suffixes[-1].lower() in COMPRESSED_SUFFIXES:
        return "".join(suffixes[-2:]).lower()
        
    return suffixes[-1].lower()

def is_genomic_file(filename: str) -> bool:
    """Returns True if the file is a recognized bioinformatics format."""
    ext = extract_full_extension(filename)
    return ext in GENOMIC_EXTENSIONS

def is_knowledge_file(filename: str) -> bool:
    """Returns True if the file is a document/image meant for Docling/RAG."""
    ext = extract_full_extension(filename)
    return ext in KNOWLEDGE_EXTENSIONS