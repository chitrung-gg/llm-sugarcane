from langchain_core.prompts import PromptTemplate
from app.schemas.agent.executor import ExecutorOutput

# 1. Define examples as Pydantic objects
_EX_ACCESSION = ExecutorOutput(
    scratchpad="The task requires extracting the NCBI identifier for the R570 cultivar. I see 'GCA_038087645.1' in the history. I will isolate this string.",
    status="SUCCESS",
    data_extracted=["GCA_038087645.1"],
    final_result="The NCBI Accession number for the R570 genome assembly is GCA_038087645.1."
)

_EX_BRIX = ExecutorOutput(
    scratchpad="The user wants genes related to 'Brix content'. Scanning context: Gene_001 and Gene_003 explicitly mention Brix. Gene_002 is unrelated.",
    status="SUCCESS",
    data_extracted=["Gene_001", "Gene_003"],
    final_result="Based on the mapping, Gene_001 (sucrose synthase) and Gene_003 (cell wall invertase) are associated with Brix content."
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

<example name="trait_mapping">
  <task>Identify which genes are associated with 'Brix content' from the provided trait mapping list.</task>
  <history>Search results returned: 'Gene_001: sucrose synthase (Brix)', 'Gene_002: chlorophyll binding', 'Gene_003: cell wall invertase (Brix)'.</history>
  <ideal_response>
{_EX_BRIX.model_dump_json(**_JSON_OPTS)}
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

### Guidelines:
* **Focus on the Current Task:** Do not try to solve the entire user query at once. Just complete the specific objective listed in `<current_task>`.
* **Use the History:** The `<conversation_history>` contains the results of previous steps. Read it carefully to find data (like gene IDs, filenames, or tool outputs) needed for your current task.
* **Be Precise:** When extracting data or identifiers, isolate them clearly in the `data_extracted` field. 
* **Graceful Failure:** If you absolutely cannot complete the task because vital information is missing from the history, set your status to 'REQUIRES_CLARIFICATION' and explain what you need.
* **Think Aloud:** Use your `scratchpad` to explain your logic before finalizing the output.

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