import json
import uuid
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.pruning import PruningOutput

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_PRUNING_OUTPUT_SCHEMA = json.dumps(PruningOutput.model_json_schema(), indent=2)

# 1. Define examples as Pydantic objects
_EX_RELEVANT_MATCH = PruningOutput(
    scratchpad=(
        "The user query focuses on sucrose metabolism in sugarcane, specifically comparing 'R570' and 'SP80-3280'. "
        "Dataset 1 contains the 'R570' genome assembly and metabolic annotations. "
        "Dataset 2 contains 'SP80-3280' genomic data. "
        "Dataset 3 (Arabidopsis thaliana) is a model organism but not requested for this specific sugarcane comparison. "
        "Result: Selecting Datasets 1 and 2."
    ),
    relevant_file_ids=[
        uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
        uuid.UUID("67123456-e29b-41d4-a716-446655440001")
    ],
    reasoning="Matched specific sugarcane cultivars (R570, SP80-3280) and their metabolic annotation files."
)

_EX_NO_MATCH = PruningOutput(
    scratchpad=(
        "The query 'What is the capital of Brazil?' is a general knowledge question and does not relate to "
        "any genomic datasets or bioinformatics research intent. No files are required to answer this."
    ),
    relevant_file_ids=[],
    reasoning="General query unrelated to attached genomic datasets."
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example_scenario name="biological_relevance">
  <user_query>Compare sucrose transporter genes between R570 and SP80-3280.</user_query>
  <ideal_response>
{_EX_RELEVANT_MATCH.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>

<example_scenario name="irrelevant_query">
  <user_query>What is the capital of Brazil?</user_query>
  <ideal_response>
{_EX_NO_MATCH.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT_STR = """
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

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{pruning_output_schema}
</output_directive>

<input_data>
<user_query>
{query}
</user_query>

<available_files>
{file_list}
</available_files>
</input_data>
"""

INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT = PromptTemplate(
    template=INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT_STR,
    input_variables=["query", "file_list"],
    partial_variables={
        "pruning_output_schema": _PRUNING_OUTPUT_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)

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
