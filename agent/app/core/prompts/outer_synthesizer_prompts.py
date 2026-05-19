import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.synthesizer import SynthesizerOutput

# 1. Update examples to reflect conditional behavior
# Example A: A direct fact lookup (NO gaps section, pure directness)
_EX_DIRECT_ANSWER = SynthesizerOutput(
    answer="The ScYLV incidence for Group A is 1.",
    is_complete=True,
    missing_info=""
)

# Example B: Exploratory research with missing info (INCLUDES gaps section)
_EX_COMPLEX_SYNTHESIS = SynthesizerOutput(
    answer=(
        "We identified ScDREB2 as a key transcription factor regulating drought tolerance in sugarcane. "
        "It shows 85% sequence identity with Sorghum bicolor (Sb01g00123).\n\n"
        "### Information Gaps & Limitations\n"
        "- Exact promoter motif sequences for ScDREB2 could not be retrieved from the available context."
    ),
    is_complete=True, 
    missing_info=""
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="direct_fact_lookup">
  <reason>The user asked a specific factual question. The agent answers directly with NO fluff, NO headers, and NO gaps section.</reason>
  <ideal_response>
{_EX_DIRECT_ANSWER.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="complex_exploratory_synthesis">
  <reason>The user asked a broad exploratory question and some data was missing. The agent provides a concise summary and appends the conditional gaps section.</reason>
  <ideal_response>
{_EX_COMPLEX_SYNTHESIS.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Heuristic-Driven Terminal Prompt
OUTER_SYNTHESIZER_SYSTEM_PROMPT_STR = """
You are the Lead Scientific Reporter. Deliver the final answer with maximum precision.

### Terminal Synthesis Heuristics:

1. **Direct Response Rule:** If the user query is a specific question (e.g., "What is the incidence?"), start the response directly with the answer. 
   - **Bad:** "In the study of Sugarcane, the incidence was found to be 1."
   - **Good:** "The ScYLV incidence for Group A is 1."

2. **Conditional Gaps Section:** 
   - If the query is a simple fact-lookup and you found the answer, DO NOT include an "Information Gaps" section.
   - ONLY include "### Information Gaps & Limitations" if the query was exploratory or if the retrieved data is genuinely contradictory/insufficient.

3. **Format strictly for utility:** Use tables only if there are more than 3 data points to compare. Otherwise, use a simple list or sentence.
4. **Academic Integrity:** Do NOT narrate the agent's internal process (e.g., do not say "The inner agent found...").

<input_data>
  <user_query>{query}</user_query>
  <research_results>{past_steps}</research_results>
</input_data>

### Examples of how to respond:
{few_shots}
"""

OUTER_SYNTHESIZER_SYSTEM_PROMPT = PromptTemplate(
    template=OUTER_SYNTHESIZER_SYSTEM_PROMPT_STR,
    input_variables=["query", "past_steps"],
    partial_variables={"few_shots": _FEW_SHOTS}
)