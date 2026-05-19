import uuid
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.input_analyzer import PruningOutput

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

### Data Relevance Heuristics (Cost vs. Value):
Evaluate each dataset using these principles:
1. **The Cost of Clutter:** Every irrelevant file dilutes the LLM's attention. If a file does not directly help answer the `<user_query>`, exclude it.
2. **High-Value Matches:** If the query specifically names a cultivar (e.g., R570), a gene, or a biological process that matches a dataset's description, that dataset is high-value. Keep it.
3. **Comparative Necessity:** If the query asks to "compare" or "align" (e.g., BLAST, Synteny), you must keep the specific reference genomes mentioned, or default reference genomes if none are explicitly named.
4. **Conversational Queries:** If the user is just saying "hello", asking general knowledge, or asking a meta-question ("how do you know that?"), the value of genomic datasets is zero. Return an empty list.

### Scratchpad Logic:
1. Analyze the core entities in the user query.
2. Weigh the relevance of each available dataset against those entities.
3. Select ONLY the UUIDs of the datasets that pass the High-Value or Comparative threshold.

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
 <usage_heuristics>
    * This is a raw bioinformatics file. It CANNOT be read as plain text.
    * BEST CAPABILITY: Pass the `s3_uri` to External Tools (like BLAST, Synteny, Primer, CRISPOR tools) (the internal tool that call backend) to extract statistics or run alignments.
  </usage_heuristics>
</system_injected_context>
""")

INPUT_ANALYZER_MASSIVE_FILE_NOTE = PromptTemplate.from_template("""
<system_injected_context type="massive_file_alert">
  <file_status>
    <filename>{file_name}</filename>
    <state>Archived in vector memory. File exceeds instant-read context limits.</state>
  </file_status>
 <usage_heuristics>
    * BEST CAPABILITY: Route to the `rag_only` intent or use Internal Knowledge tools (related to Knowledge Graph) to query the contents of this document. 
  </usage_heuristics>
</system_injected_context>
""")

INPUT_ANALYZER_FILE_CONTEXT_HEADER = PromptTemplate.from_template("""
<uploaded_file_context>
INSTRUCTION: The user has attached the following file data. Treat this as the primary ground-truth context for fulfilling their query.
---
""")