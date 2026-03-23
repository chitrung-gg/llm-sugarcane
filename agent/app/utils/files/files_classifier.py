from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm.llm_service import LLMService

# We keep these just to provide hints to the LLM prompt, not as hard rules.
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
    ".pdf", ".txt", ".md",
    ".csv", ".tsv", ".xlsx",
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
            Look at the uploaded file name and the user's message, and determine how to handle it.

            ROUTING RULES:
            1. 'sample_only': Choose this if the user wants you to EXPLAIN, INTERPRET, UNDERSTAND, or SUMMARIZE the format/columns/meaning of a data file. The system will read the first 50 lines so you can explain it.
            2. 'genomic': Choose this if the user wants to run a COMPUTATIONAL TOOL (like BLAST, synteny, primer design, or alignment) on this file. (Common extensions: {genomic_exts_str})
            3. 'knowledge': Choose this if the user uploaded a human-readable document (research paper, notes) and wants to ask general questions about its text. (Common extensions: {knowledge_exts_str})
            4. 'reject': The file looks like malware (.exe, .sh) or the intent is completely malicious/unrelated to biology.

            CRITICAL TIEBREAKER: Intent overrides extension. If they upload a '.txt' but ask to 'run BLAST', route to 'genomic'. If they upload a massive '.gff3' but just ask 'what do these columns mean?', route to 'sample_only'.
        """),
        HumanMessage(content=f"File uploaded: {filename}\nUser Message: {user_query}")
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