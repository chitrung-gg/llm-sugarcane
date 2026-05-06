from langchain_core.prompts import PromptTemplate
from app.schemas.agent.summarizer import SummaryOutput

# 1. Define examples as Pydantic objects
_EX_SUMMARY = SummaryOutput(
    new_summary="The user is analyzing the polyploid genome of Saccharum spontaneum var R570. They uploaded file s3://rustfs/R570_assembly.fasta and successfully ran a BLAST search for gene ScDREB2 with e-value: 1e-5. They are now investigating drought-related orthologs."
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="high_fidelity_summary">
  <ideal_response>
{_EX_SUMMARY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Loosened System Prompt
SUMMARIZER_SYSTEM_PROMPT_STR = """
You are a technical Research Archivist specializing in Sugarcane Bioinformatics. Your task is to compress the preceding conversation into a dense, high-fidelity summary that serves as the primary context for future autonomous agents.

<instructions>
{summary_message}
</instructions>

### Guidelines:
* **Lossless Identifiers:** Always retain specific technical identifiers. You must preserve Gene IDs, Protein Accessions, NCBI/EMBL-EBI Accession numbers (e.g., GCA_..., PRJNA...), S3 URIs, filenames, and DOIs.
* **Biological Specificity:** Be exact with biological entities. Instead of generalizing to "the user asked about a sugarcane cultivar," specifically state "the user analyzed Saccharum spontaneum var R570."
* **Tool Context:** Keep a record of specific tool parameters or arguments discussed (e.g., 'e-value: 1e-5', 'qcov_hsp_perc: 80') as they may be required for future query refinement.
* **Concise Utility:** Prioritize technical utility and data density over narrative flow. It is perfectly fine to write in fragmented shorthand if it maximizes information retention.

### Example Response:
{few_shots}
"""

# Schema injection removed entirely
SUMMARIZER_SYSTEM_PROMPT = PromptTemplate(
    template=SUMMARIZER_SYSTEM_PROMPT_STR,
    input_variables=["summary_message"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)