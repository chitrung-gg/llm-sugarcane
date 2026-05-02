from langchain_core.prompts import PromptTemplate

INPUT_ANALYZER_GENOMIC_FILE_NOTE = PromptTemplate.from_template("""
<system_injected_context type="genomic_dataset_attachment">
  <file_metadata>
    <filename>{file_name}</filename>
    <s3_uri>{rustfs_uri}</s3_uri>
    <description>{description}</description>
  </file_metadata>
  <strict_execution_rules>
    1. DIRECT ACCESS DENIED: You cannot read the raw contents of this file directly into your context window.
    2. TOOL USAGE REQUIRED: To analyze this dataset, you MUST pass the exact S3 URI (`{rustfs_uri}`) as an argument to a compatible backend tool (e.g., `run_blast`).
    3. NO HALLUCINATION: If the user requests metrics (e.g., N50, GC content) and you lack a specific tool to compute them from the S3 URI, you MUST explicitly state that you lack the capability. Do not invent, estimate, or infer statistics.
  </strict_execution_rules>
</system_injected_context>
""")

INPUT_ANALYZER_MASSIVE_FILE_NOTE = PromptTemplate.from_template("""
<system_injected_context type="massive_file_alert">
  <file_status>
    <filename>{file_name}</filename>
    <state>Archived in vector memory. File exceeds instant-read context limits.</state>
  </file_status>
  <routing_directive>
    MANDATORY ACTION: You MUST route the upcoming execution to either the 'rag_only' or 'all' pathways. Standard processing will fail.
  </routing_directive>
</system_injected_context>
""")

INPUT_ANALYZER_FILE_CONTEXT_HEADER = PromptTemplate.from_template("""
<uploaded_file_context>
INSTRUCTION: The user has explicitly attached the following file data. Treat this data as the primary ground-truth context for fulfilling their query.
---
""")