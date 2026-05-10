from langchain_core.prompts import PromptTemplate
from app.schemas.agent.web_search import OptimizedSearchQuery

# 1. Define examples as Pydantic objects 
_EX_METABOLIC = OptimizedSearchQuery(
    search_query="sugarcane Saccharum SP80-3280 metabolic response drought stress research study"
)

_EX_COMPARATIVE = OptimizedSearchQuery(
    search_query="Saccharum hybrid R570 Sorghum bicolor comparative genomics synteny analysis"
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

# 2. The Heuristic-Driven System Prompt
WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR = """
You are the Web Search Architect for a Bioinformatics Intelligence System. Your objective is to transform conversational user input into a highly targeted search engine query (for tools like Google Scholar, PubMed, or SearxNG).

<input_data>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <user_question>{user_question}</user_question>
</input_data>

### Web Search Optimization Heuristics:
1. **Domain Anchoring (Avoid Web Noise):** The public web is vast and contains human medical data, pop culture, and generic botany. You MUST anchor every query with explicit domain keywords (e.g., "sugarcane", "Saccharum") so the search engine filters out unrelated organisms.
2. **Entity Resolution (Context Preservation):** Search engines cannot read our chat history. Replace all ambiguous pronouns (e.g., "this gene", "that paper", "the variety") in the user's question with explicit identifiers from the `<conversation_summary>`.
3. **Search Engine Dynamics (Keywords over Syntax):** Search engines rely on exact word matching and frequency. Strip all conversational filler ("I would like to know", "What does the literature say about"). Prioritize dense biological nouns, cultivar names, and technical metrics (e.g., "synteny", "polyploidy", "QTL mapping").
4. **Academic Targeting:** If the user implies finding literature or studies, include functional keywords that surface academic papers (e.g., "research", "study", "analysis", "genomics").

### Examples of how to respond:
{few_shots}
"""

# Schema injection removed; LangChain handles it natively.
WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT = PromptTemplate(
    template=WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR,
    input_variables=["conversation_summary", "user_question"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)