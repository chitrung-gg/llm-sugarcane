from langchain_core.prompts import PromptTemplate
from app.schemas.agent.summarizer import SummaryOutput

# 1. Define examples as Pydantic objects
_EX_SUMMARY = SummaryOutput(
    new_summary="User analyzing polyploid genome Saccharum spontaneum var R570. Uploaded: s3://rustfs/R570_assembly.fasta. Completed BLAST search for ScDREB2 (e-value: 1e-5). Current objective: Investigate drought-related orthologs based on BLAST results."
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="high_fidelity_state_compression">
  <reason>Demonstrates flawless retention of S3 URIs, exact taxonomy, and tool parameters while dropping conversational fluff.</reason>
  <ideal_response>
{_EX_SUMMARY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Heuristic-Driven System Prompt
SUMMARIZER_SYSTEM_PROMPT_STR = """
You are the Context Compression Engine for a Sugarcane Bioinformatics system. Your task is to compress the preceding conversation into a dense, high-fidelity summary that serves as the "Long-Term Memory" for downstream autonomous agents.

<instructions>
{summary_message}
</instructions>

### State Compression Heuristics (Value vs. Noise):
1. **Immutable Anchors (Maximum Value):** Downstream API tools will fail without exact IDs. You MUST losslessly preserve all Gene IDs, Protein Accessions, NCBI/EMBL Accession numbers (e.g., GCA_...), S3 URIs, filenames, and DOIs.
2. **Biological Precision (High Value):** Generalizations break research pipelines. Instead of "the user asked about a sugarcane cultivar," strictly preserve the exact taxonomy (e.g., "Saccharum spontaneum var R570").
3. **Execution State (Medium Value):** Downstream planners need to know what work is already done to avoid infinite loops. Briefly note successful tool calls and their hard parameters (e.g., "Executed BLAST with e-value 1e-5"). 
4. **Conversational Fluff (Zero Value):** Remove all pleasantries, apologies, and intermediate reasoning steps ("The user said hi", "I am now searching for..."). 

### Formatting Rule:
Prioritize raw technical utility and data density over narrative flow. It is perfectly fine to write in fragmented shorthand if it maximizes information retention and minimizes token count.

### Example Response:
{few_shots}
"""

# Schema injection removed entirely; LangChain handles it natively via structured output.
SUMMARIZER_SYSTEM_PROMPT = PromptTemplate(
    template=SUMMARIZER_SYSTEM_PROMPT_STR,
    input_variables=["summary_message"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)