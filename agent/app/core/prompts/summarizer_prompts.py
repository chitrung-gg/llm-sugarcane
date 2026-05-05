import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.summarizer import SummaryOutput

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_SUMMARY_OUTPUT_SCHEMA = json.dumps(SummaryOutput.model_json_schema(), indent=2)

# 1. Define examples as Pydantic objects
_EX_SUMMARY = SummaryOutput(
    new_summary="The user is analyzing the polyploid genome of Saccharum spontaneum var R570. They uploaded file s3://rustfs/R570_assembly.fasta and successfully ran a BLAST search for gene ScDREB2 with e-value: 1e-5. They are now investigating drought-related orthologs."
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example_scenario name="high_fidelity_summary">
  <ideal_response>
{_EX_SUMMARY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

SUMMARIZER_SYSTEM_PROMPT = PromptTemplate(
    template="""
<role>
You are a technical Research Archivist specializing in Sugarcane Bioinformatics.
Your task is to compress the preceding conversation into a dense, high-fidelity summary that serves as the primary context for future autonomous agents.
</role>

<instructions>
{summary_message}
</instructions>

<strict_preservation_rules>
1. LOSSLESS IDENTIFIERS: You are FORBIDDEN from omitting or generalizing technical identifiers. You MUST retain:
   - Gene IDs and Protein Accessions.
   - NCBI/EMBL-EBI Accession numbers (e.g., GCA_..., PRJNA...).
   - S3 URIs and file paths (e.g., s3://rustfs/...).
   - DOIs and specific citation keys.
2. BIOLOGICAL SPECIFICITY: Do not generalize biological entities. 
   - FAIL: "The user asked about a sugarcane cultivar."
   - PASS: "The user analyzed the polyploid genome of Saccharum spontaneum var R570."
3. TOOL ARGUMENT PERSISTENCE: Retain any specific tool parameters or arguments discussed (e.g., 'e-value: 1e-5', 'qcov_hsp_perc: 80') as they may be required for query refinement.
4. CONCISION VS. UTILITY: Prioritize technical utility over narrative flow. Use bullet points for entity lists to maximize scannability.
</strict_preservation_rules>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{summary_output_schema}
</output_directive>
""",
    input_variables=["summary_message"],
    partial_variables={
        "summary_output_schema": _SUMMARY_OUTPUT_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)