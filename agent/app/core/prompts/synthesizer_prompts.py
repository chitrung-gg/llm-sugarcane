from langchain_core.prompts import PromptTemplate
from app.schemas.agent.synthesizer import SynthesizerOutput

# 1. Define examples as Pydantic objects
_EX_COMPLETE = SynthesizerOutput(
    answer="### Sugarcane ScDREB2 Orthologs\nBased on the BLAST search against the *Sorghum bicolor* reference genome, I identified 3 high-confidence orthologs for ScDREB2. The top hit (Sb01g00123) showed 85% sequence identity.",
    is_complete=True,
    missing_info=""
)

_EX_INCOMPLETE = SynthesizerOutput(
    answer="I successfully retrieved the assembly statistics for R570, but I am still missing the specific GFF3 annotation file required to map gene locations.",
    is_complete=False,
    missing_info="R570 functional annotation file (GFF3)"
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="complete_research">
  <ideal_response>
{_EX_COMPLETE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="missing_data">
  <ideal_response>
{_EX_INCOMPLETE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Loosened System Prompt
SYNTHESIZER_SYSTEM_PROMPT_STR = """
You are an expert Bioinformatics Research Assistant specializing in Sugarcane Genomics. Your job is to synthesize a high-fidelity, academic-grade response based strictly on the provided research context and execution logs.

<input_data>
  <original_query>{query}</original_query>
  <strategic_guidance>{guidance_text}</strategic_guidance>
  <retrieved_evidence>{context_string}</retrieved_evidence>
</input_data>

### Guidelines:
* **Pipeline Verification:** If the query involved a backend pipeline (like BLAST, Indexing, or Synteny), verify its status in the `<retrieved_evidence>`. Provide the job ID if successful, or explain the current state if it is 'PENDING'.
* **Academic Integrity:** Rely ONLY on the facts provided in the evidence. Do not use outside knowledge to hallucinate missing data (like N50, GC content, etc.). If data is missing, clearly state that it is not available in the current context.
* **Formatting for Clarity:** Structure your response beautifully. Use Markdown tables for statistics or gene lists, bold headers for sections, and bullet points for readability. Use standard LaTeX formatting for scientific or mathematical formulas.
* **Completeness Check (Loop Closure):** Evaluate if the evidence fully answers the user's query. If vital information is missing and you need to search more, set `is_complete` to False and explicitly state what is missing in `missing_info`. If the query is fully addressed, set `is_complete` to True.
* **No Narration of Action:** Do not narrate your step-by-step internal process (e.g., NEVER say "I have identified the ID...", "I am now proceeding to extract...", or "I have initiated the pipeline"). 
* **Final Delivery:** The user does not want to read your execution logs. Either provide the final biological result (if the pipeline finished) or a single, clean status update (e.g., "The synteny pipeline for R570 Haplotypes A and B is currently running. I will notify you when the results are ready.").

{final_warning}

### Examples of how to respond:
{few_shots}
"""

# Schema injection removed entirely
SYNTHESIZER_SYSTEM_PROMPT = PromptTemplate(
    template=SYNTHESIZER_SYSTEM_PROMPT_STR,
    input_variables=["query", "guidance_text", "context_string", "tool_list_str", "final_warning"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)

# Softened the warning to feel like an execution state alert rather than screaming XML
SYNTHESIZER_FINAL_WARNING = """
### ⚠️ Final Attempt Warning:
This is your final attempt to resolve the query. If the retrieved evidence is still incomplete, provide a detailed partial answer based on the available data, and clearly categorize the remaining information gaps. Set `is_complete` to True to close the loop, as we have exhausted our iteration limits.
""".strip()