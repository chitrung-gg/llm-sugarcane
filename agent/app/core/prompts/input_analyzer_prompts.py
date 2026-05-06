import uuid
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.pruning import PruningOutput

# 1. Define examples as Pydantic objects
_EX_RELEVANT_MATCH = PruningOutput(
    scratchpad=(
        "The user query focuses on sucrose metabolism in sugarcane, specifically comparing 'R570' and 'SP80-3280'. "
        "Dataset 1 contains 'R570' and Dataset 2 contains 'SP80-3280'. "
        "Dataset 3 is Arabidopsis (irrelevant here). "
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
        "The query 'What is the capital of Brazil?' is general knowledge and does not relate to "
        "genomic datasets. No files are required."
    ),
    relevant_file_ids=[],
    reasoning="General query unrelated to attached genomic datasets."
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="biological_relevance">
  <user_query>Compare sucrose transporter genes between R570 and SP80-3280.</user_query>
  <ideal_response>
{_EX_RELEVANT_MATCH.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="irrelevant_query">
  <user_query>What is the capital of Brazil?</user_query>
  <ideal_response>
{_EX_NO_MATCH.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Loosened System Prompt
INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT_STR = """
You are the Biological Context Pruning Specialist. Your job is to review a user's query against a list of available genomic datasets and identify ONLY the files that are strictly necessary to fulfill the request.

<input_data>
<user_query>
{query}
</user_query>

<available_files>
{file_list}
</available_files>
</input_data>

### Guidelines:
* **Biological Validity:** If the query is just a greeting, general knowledge, or nonsensical, simply select zero files.
* **Direct Matches:** Include files that explicitly mention the cultivars (e.g., R570, SP80-3280), genes, or organisms mentioned in the query.
* **Functional Necessity:** Include reference genomes if the query implies a comparative analysis, alignment (BLAST), or synteny mapping.
* **Parsimony Principle:** When in doubt, exclude the file. We want to maximize context space by removing low-relevance metadata.
* **Think Aloud:** Use your `scratchpad` to briefly justify why each selected file is mandatory for the research goal before outputting the UUIDs.

### Example Responses:
{few_shots}
"""

# Schema injection removed, LangChain's structured output will handle it natively.
INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT = PromptTemplate(
    template=INPUT_ANALYZER_PRUNING_SYSTEM_PROMPT_STR,
    input_variables=["query", "file_list"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)


# ------------------------------------------------------------------
# Downstream System Injection Notes
# ------------------------------------------------------------------

# Softened from <strict_execution_rules> to <execution_guidelines> 
# to prevent downstream ReAct agents from freezing up due to rigid constraints.
INPUT_ANALYZER_GENOMIC_FILE_NOTE = PromptTemplate.from_template("""
<system_injected_context type="genomic_dataset_attachment">
  <file_metadata>
    <filename>{file_name}</filename>
    <s3_uri>{rustfs_uri}</s3_uri>
    <description>{description}</description>
  </file_metadata>
  <execution_guidelines>
    * DIRECT ACCESS LIMITATION: You cannot read the raw contents of this file directly into your context window.
    * TOOL USAGE REQUIRED: To analyze this dataset, you must pass the exact S3 URI (`{rustfs_uri}`) as an argument to a compatible backend tool.
    * NO HALLUCINATIONS: If asked for metrics you cannot compute with available tools, explicitly state your limitations. Do not guess or estimate statistics.
  </execution_guidelines>
</system_injected_context>
""")

INPUT_ANALYZER_MASSIVE_FILE_NOTE = PromptTemplate.from_template("""
<system_injected_context type="massive_file_alert">
  <file_status>
    <filename>{file_name}</filename>
    <state>Archived in vector memory. File exceeds instant-read context limits.</state>
  </file_status>
  <routing_directive>
    * PREFERRED PATHWAY: Route upcoming executions involving this file to the 'rag_only' or 'all' pathways to search the vector memory.
  </routing_directive>
</system_injected_context>
""")

INPUT_ANALYZER_FILE_CONTEXT_HEADER = PromptTemplate.from_template("""
<uploaded_file_context>
INSTRUCTION: The user has attached the following file data. Treat this as the primary ground-truth context for fulfilling their query.
---
""")