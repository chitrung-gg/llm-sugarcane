from langchain_core.prompts import PromptTemplate
from app.schemas.agent.web_search import OptimizedSearchQuery

# 1. Define examples as Pydantic objects 
_EX_METABOLIC = OptimizedSearchQuery(
    search_query="SP80-3280 sugarcane Saccharum metabolic response drought stress research papers 2024..2026"
)

_EX_COMPARATIVE = OptimizedSearchQuery(
    search_query="Saccharum hybrid R570 vs Sorghum bicolor genome comparative synteny analysis"
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="metabolic_research">
  <conversation_summary>Discussing drought resistance in sugarcane cultivar SP80-3280.</conversation_summary>
  <user_question>Find more recent papers on its metabolic response.</user_question>
  <ideal_response>
{_EX_METABOLIC.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="comparative_genomics">
  <conversation_summary>User is researching the R570 genome assembly.</conversation_summary>
  <user_question>Are there any studies comparing it to the sorghum genome?</user_question>
  <ideal_response>
{_EX_COMPARATIVE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Loosened System Prompt
WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR = """
You are an expert Search Query Optimizer for Bioinformatics and Genomic Research. Your objective is to transform conversational user input into a precise, keyword-dense search engine query optimized for academic and technical retrieval.

<conversation_summary>
{conversation_summary}
</conversation_summary>

<user_question>
{user_question}
</user_question>

### Guidelines:
* **Entity Resolution:** Replace ambiguous pronouns (e.g., "this gene", "that paper", "the variety") in the user's question with explicit identifiers from the `<conversation_summary>`.
* **Species Anchoring:** If the context involves sugarcane, ensure terms like "Saccharum", "Saccharum officinarum", or "Saccharum spontaneum" are included to filter out irrelevant plant results.
* **Remove Fluff:** Strip all conversational filler like "I would like to know", "Search for", or "What does the literature say about".
* **Keyword Density:** Prioritize biological nouns, cultivar names, and technical metrics (e.g., "synteny", "polyploidy", "QTL mapping") over natural language questions.

### Examples of how to respond:
{few_shots}
"""

# Schema injection removed entirely
WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT = PromptTemplate(
    template=WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR,
    # BUG FIX: Added user_question so the LLM actually sees what it needs to optimize!
    input_variables=["conversation_summary", "user_question"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)