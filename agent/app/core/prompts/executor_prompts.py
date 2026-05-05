import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.executor import ExecutorOutput

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_EXECUTOR_OUTPUT_SCHEMA = json.dumps(ExecutorOutput.model_json_schema(), indent=2)

# 1. Define examples as Pydantic objects
_EX_ACCESSION = ExecutorOutput(
    scratchpad="The task requires extracting a specific NCBI identifier for the R570 cultivar. I see 'GCA_038087645.1' in the context. I will isolate this string as the primary data point.",
    status="SUCCESS",
    data_extracted=["GCA_038087645.1"],
    final_result="The NCBI Accession number for the R570 genome assembly is GCA_038087645.1."
)

_EX_BRIX = ExecutorOutput(
    scratchpad="The user wants genes related to 'Brix content'. Scanning context for this keyword. Gene_001 and Gene_003 explicitly mention Brix in their annotations. Gene_002 is unrelated to sugar content.",
    status="SUCCESS",
    data_extracted=["Gene_001", "Gene_003"],
    final_result="Based on the mapping, Gene_001 (sucrose synthase) and Gene_003 (cell wall invertase) are associated with Brix content."
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example_scenario name="identifier_extraction">
  <task>Extract the NCBI Accession number for the R570 genome assembly mentioned in the context.</task>
  <context>The user is analyzing the Saccharum hybrid R570. Previous steps retrieved the assembly metadata including the identifier GCA_038087645.1.</context>
  <ideal_response>
{_EX_ACCESSION.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>

<example_scenario name="trait_mapping">
  <task>Identify which genes are associated with 'Brix content' from the provided trait mapping list.</task>
  <context>Search results returned: 'Gene_001: sucrose synthase (Brix)', 'Gene_002: chlorophyll binding', 'Gene_003: cell wall invertase (Brix)'.</context>
  <ideal_response>
{_EX_BRIX.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

EXECUTOR_INNER_QUERY_PROMPT_STR = """
<role>
You are an expert Sugarcane Genomics Chatbot Agent. Your objective is to accurately execute specific sub-tasks within a bioinformatics research workflow, focusing on genomic data, sugarcane cultivars (e.g., R570, SP80-3280), and molecular breeding research.
</role>

<context>
  <previous_context>
  {history_context}
  </previous_context>

  <current_task>
  {step_description}
  </current_task>
</context>

<instructions>
1. Review the <previous_context> to identify existing biological data, cultivar names, or tool outputs.
2. Analyze the <current_task> to determine the specific extraction or analysis required.
3. Use the <scratchpad> for your Chain-of-Thought reasoning. State your logic before committing to the output.
4. If the data required for the task is missing from the context, set status to 'REQUIRES_CLARIFICATION' and explain what is missing.
</instructions>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{executor_output_schema}
</output_directive>
"""

EXECUTOR_INNER_QUERY_PROMPT = PromptTemplate(
    template=EXECUTOR_INNER_QUERY_PROMPT_STR,
    input_variables=["step_description", "history_context"],
    partial_variables={
        "executor_output_schema": _EXECUTOR_OUTPUT_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)
