from langchain_core.prompts import PromptTemplate

SUMMARIZER_SYSTEM_PROMPT = PromptTemplate.from_template(
    """
    {summary_message}

    CRITICAL RULES:
    1. Retain ALL strict factual data: Gene IDs, NCBI accessions, file names, S3 URIs, and tool arguments.
    2. Do not generalize specific biological entities (e.g., keep 'Saccharum spontaneum var R570', do not just say 'a sugarcane plant').
    3. Keep it concise, but NEVER drop technical constraints required for future database searches.
    """
)