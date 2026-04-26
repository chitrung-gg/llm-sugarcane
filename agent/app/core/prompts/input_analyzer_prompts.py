from langchain_core.prompts import PromptTemplate

INPUT_ANALYZER_GENOMIC_FILE_NOTE = PromptTemplate.from_template(
    """
    [SYSTEM NOTE: The user uploaded a heavy bioinformatics dataset '{file_name}'.
    S3 URI: {rustfs_uri}
    Description: {description}

    CRITICAL: You CANNOT read this file directly. To process this file, you MUST pass this exact S3 URI (`{rustfs_uri}`) into the arguments of a compatible backend tool (e.g., `run_blast`). If the user asks for statistics (like N50 or GC content) and you do not have a specific tool to calculate them from an S3 URI, you MUST inform the user that you lack the required tool. DO NOT hallucinate stats.]
    """
)

INPUT_ANALYZER_MASSIVE_FILE_NOTE = PromptTemplate.from_template(
    """
    [SYSTEM NOTE: The uploaded file '{file_name}' was too large to read instantly. It is stored in temporary memory. You MUST route to 'rag_only' or 'all' to augment it.]
    """
)

INPUT_ANALYZER_FILE_CONTEXT_HEADER = PromptTemplate.from_template(
    """
    The user has uploaded the following files for context. Use this information to answer their query:\n\n
    """
)
