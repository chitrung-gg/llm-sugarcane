from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm.llm_service import LLMService

# Keep these just to provide hints to the LLM prompt, not as hard rules.
GENOMIC_EXTENSIONS = {
    ".fasta.gz", ".fa.gz", ".fna.gz",
    ".genome.fasta.gz", ".genome.fa.gz",
    ".gene.fasta.gz", ".gene.fa.gz",
    ".protein.fasta.gz", ".protein.fa.gz"
    ".cds.fasta.gz", ".cds.fa.gz",
    ".pep.fasta.gz",
    ".gff3.gz", ".gff.gz", ".gtf.gz",
    ".vcf.gz", ".bed.gz", 
}

KNOWLEDGE_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", 
    ".html", ".epub", ".msg", ".eml", ".rtf", ".odt", ".md", 
    ".tex", ".csv", ".png", ".jpeg"
}


class FileClassification(BaseModel):
    category: Literal["genomic", "knowledge", "sample_only", "reject"] = Field(
        description="The routing category for the uploaded file."
    )
    reason: str = Field(
        description="A short explanation of why this category was chosen based on user intent."
    )

async def classify_upload_with_llm(
    filename: str, 
    user_query: str, 
    llm_service: LLMService
) -> Literal["genomic", "knowledge", "sample_only", "reject"]:
    """
    Uses a fast LLM to dynamically determine file routing based on user intent.
    """
    llm = llm_service.get_secondary_model()
    structured_llm = llm.with_structured_output(FileClassification)

    # 1. Pre-format your variables
    genomic_exts_str = ", ".join(GENOMIC_EXTENSIONS)
    knowledge_exts_str = ", ".join(KNOWLEDGE_EXTENSIONS)

    # 2. Use native Python f-strings inside SystemMessage and HumanMessage
    messages = [
        SystemMessage(content=f"""
            You are an intelligent file routing system for a Bioinformatics platform.
            Look at the specific uploaded file name and the user's message, and determine how to handle it.

            ROUTING RULES:
            1. 'sample_only': Choose this if the user wants to EXPLAIN, INTERPRET, UNDERSTAND, or SUMMARIZE the format, headers, or columns of a data file.
            2. 'genomic': Choose this if the user explicitly wants to run a HEAVY COMPUTATIONAL BACKEND TOOL (like BLAST, synteny, mapping, Airflow pipelines) on this file. (Common: {genomic_exts_str})
            3. 'knowledge': Choose this for human-readable documents (papers, notes) OR if the user wants you (the LLM) to directly read, translate, or analyze a small text/sequence file. (Common: {knowledge_exts_str})
            4. 'reject': The file looks like malware (.exe, .sh) or the intent is completely unrelated to biology/system tasks.

            CRITICAL EDGE CASES:
            - EMPTY/VAGUE QUERIES: If the user message is empty or generic ("here", "process this"), rely heavily on the file extension. Route documents to 'knowledge' and genomic datasets to 'genomic'.
            - MULTI-FILE CONTEXT: The user may have uploaded multiple files. If the user says "Run BLAST with the parameters in the PDF", evaluate THIS specific file. The PDF goes to 'knowledge' (to read parameters), and the FASTA goes to 'genomic'.
            - INTENT OVER EXTENSION: If they upload a '.txt' but ask to 'run BLAST', route to 'genomic'. If they upload a massive '.gff3' but just ask 'what do these columns mean?', route to 'sample_only'.
        """),
        HumanMessage(content=f"File being evaluated: {filename}\nUser Message: {user_query or '[NO MESSAGE PROVIDED]'}")
    ]

    try:
        # 3. Pass the message list directly to the structured LLM
        raw_result = await structured_llm.ainvoke(messages)
        result = FileClassification.model_validate(raw_result)
        
        logger.info(f"[File Classifier] Routed '{filename}' to {result.category}. Reason: {result.reason}")
        return result.category
        
    except Exception as e:
        logger.error(f"[File Classifier] LLM failed: {e}. Falling back to strict extension checking.")
        return _fallback_classifier(filename, user_query)


def _fallback_classifier(filename: str, user_query: str) -> Literal["genomic", "knowledge", "sample_only", "reject"]:
    """Fallback in case the LLM API fails."""
    name = filename.lower()
    query_words = set(user_query.lower().split())
    
    interpret_keywords = {"explain", "interpret", "what", "how", "structure", "format", "columns"}
    if query_words & interpret_keywords:
        return "sample_only"

    if any(name.endswith(ext) for ext in GENOMIC_EXTENSIONS):
        return "genomic"
    if any(name.endswith(ext) for ext in KNOWLEDGE_EXTENSIONS):
        return "knowledge"
    return "reject"