from langchain_core.prompts import PromptTemplate
from app.schemas.agent.executor import ExecutorOutput

# 1. Define examples as Pydantic objects
_EX_ACCESSION = ExecutorOutput(
    scratchpad="The task requires extracting the NCBI identifier for the R570 cultivar. I see 'GCA_038087645.1' in the history. I will isolate this string.",
    status="SUCCESS",
    data_extracted=["GCA_038087645.1"],
    final_result="The NCBI Accession number for the R570 genome assembly is GCA_038087645.1."
)

_EX_META_EXEC = ExecutorOutput(
    scratchpad="The task is to extract citations and sources used in the previous step. Looking at the <conversation_history>, I see the data came from 'Qdrant Vector Search' which retrieved chunks from 'sugarcane_zz1_study.pdf'. No external tools are needed.",
    status="SUCCESS",
    data_extracted=["sugarcane_zz1_study.pdf"],
    final_result="The previous answer was synthesized using internal RAG results, specifically referring to the document 'sugarcane_zz1_study.pdf'."
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="identifier_extraction">
  <task>Extract the NCBI Accession number for the R570 genome assembly mentioned in the context.</task>
  <history>The user is analyzing the Saccharum hybrid R570. Previous steps retrieved the assembly metadata including the identifier GCA_038087645.1.</history>
  <ideal_response>
{_EX_ACCESSION.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="internal_memory_extraction">
  <task>Review the previous execution history and RAG context to extract the exact document names used to formulate the previous answer.</task>
  <history>Step 1: Extracted genes from user uploaded document 'sugarcane_zz1_study.pdf'.</history>
  <ideal_response>
{_EX_META_EXEC.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Loosened, Goal-Oriented Prompt
EXECUTOR_INNER_QUERY_PROMPT_STR = """
You are the Execution Agent for a Sugarcane Genomics system. Your job is to complete the specific sub-task assigned to you by the Planner.

<conversation_history>
{history_context}
</conversation_history>

<current_task>
{step_description}
</current_task>

### Execution Philosophy & Tool Hierarchy:
Evaluate the `<current_task>` and select your action based on this strict cost hierarchy:

1. **Tier 0 (Zero Cost - No Tools):** If the task asks to extract a citation, review sources, or parse data that ALREADY EXISTS in the `<conversation_history>`, **DO NOT USE ANY TOOLS**. Just read the history and output the answer directly, unless explicitly required to rerun the tools.
2. **Tier 1 (Internal Proprietary Tools):** If the data is not in the history, use internal tools to securely search our Neo4j graph and vector databases for genes, relationships, and traits.
3. **Tier 2 (External Bio-APIs):** Use heavy external tools (like `search_ncbi_genome` or Web Search) ONLY when Tier 1 tools fail to find the specific identifier, or when the task explicitly requires fetching brand new external biological metadata.

### Execution Guidelines:
* **Focus on the Current Task:** Do not try to solve the entire user query at once. Just complete the specific objective listed in `<current_task>`.
* **Data Chaining:** If the `<current_task>` tells you to use data from a previous step, look closely at the `<conversation_history>` to find that exact data before executing your tool.
* **Be Precise:** When extracting data, IDs, or filenames, isolate them clearly in the `data_extracted` list so downstream steps can use them.
* **Graceful Failure:** If a tool fails or returns empty, DO NOT blindly repeat the exact same call. Switch to a Tier 2 tool or set your status to 'FAILED' and explain what is missing.

### Examples of how to respond:
{few_shots}
"""

# Notice that `executor_output_schema` has been completely removed.
EXECUTOR_INNER_QUERY_PROMPT = PromptTemplate(
    template=EXECUTOR_INNER_QUERY_PROMPT_STR,
    input_variables=["step_description", "history_context"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)