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

INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT = PromptTemplate.from_template("""
<role>
You are a Biological Context Pruning Specialist. Your task is to analyze a user query against a list of available genomic datasets and identify ONLY the files strictly necessary for fulfilling the request.
</role>

<instructions>
1. BIOLOGICAL VALIDITY CHECK: First, determine if the <user_query> contains valid biological entities (genes, cultivars, accessions) or research intent. If the query is gibberish or nonsensical, select ZERO files.
2. DIRECT MATCHING: Include files that explicitly mention the cultivars (e.g., R570, SP80-3280), genes, or organisms in the query.
3. FUNCTIONAL NECESSITY: Include reference genomes (e.g., Sorghum bicolor, Saccharum spontaneum) if the query implies a comparative analysis, alignment (BLAST), or synteny mapping.
4. PARSIMONY PRINCIPLE: When in doubt, exclude. The goal is to maximize context space by removing low-relevance metadata.
5. CHAIN-OF-THOUGHT: Use the <scratchpad> to justify why each selected file is mandatory for the specific research goal.
</instructions>

<few_shot_examples>
  <example>
    <user_query>Analyze drought-related genes in SP80-3280 compared to R570.</user_query>
    <available_files>
      - id: 550e8400-e29b-41d4-a716-446655440000, name: "SP80-3280_assembly.fasta", desc: "Genome assembly for cultivar SP80-3280"
      - id: 67123456-e29b-41d4-a716-446655440001, name: "R570_functional_annotation.gff3", desc: "Annotations for R570"
      - id: 78234567-e29b-41d4-a716-446655440002, name: "Arabidopsis_thaliana_ref.fna", desc: "Reference genome for Thale Cress"
    </available_files>
    <ideal_response>
      {{
        "scratchpad": "The query requires a comparison between two specific sugarcane cultivars: SP80-3280 and R570. File 550e8400-e29b-41d4-a716-446655440000 (SP80 assembly) and File 67123456-e29b-41d4-a716-446655440001 (R570 annotations) are direct matches. File 78234567-e29b-41d4-a716-446655440002 is unrelated to sugarcane genomics and is excluded.",
        "relevant_file_ids": ["550e8400-e29b-41d4-a716-446655440000", "67123456-e29b-41d4-a716-446655440001"],
        "reasoning": "Selected target cultivar assembly and comparative cultivar annotations."
      }}
    </ideal_response>
  </example>
</few_shot_examples>

<input_data>
<user_query>
{query}
</user_query>

<available_files>
{file_list}
</available_files>
</input_data>
""")