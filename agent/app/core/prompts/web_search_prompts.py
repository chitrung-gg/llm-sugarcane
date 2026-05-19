from langchain_core.prompts import PromptTemplate
from app.schemas.agent.web_search import OptimizedSearchQuery

# 1. Define examples showing the LLM actively targeting trusted sources
_EX_INCIDENCE = OptimizedSearchQuery(
    search_query="ScYLV incidence leaf Group A sugarcane data filetype:pdf"
)

_EX_COMPARATIVE = OptimizedSearchQuery(
    search_query="Saccharum hybrid R570 Sorghum bicolor comparative genomics synteny analysis"
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="incidence_data_lookup">
  <conversation_summary>User is looking for specific incidence rates.</conversation_summary>
  <user_question>What is A.SCYlV incidence.leaf for Group A?</user_question>
  <ideal_response>
{_EX_INCIDENCE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="comparative_genomics_study">
  <conversation_summary>User is researching the R570 genome assembly.</conversation_summary>
  <user_question>Are there any studies comparing it to the sorghum genome?</user_question>
  <ideal_response>
{_EX_COMPARATIVE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Heuristic-Driven System Prompt
WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR = """
You are the Web Search Architect for a Bioinformatics Intelligence System. Your objective is to generate highly targeted search engine queries that ONLY retrieve trusted, primary source data.

<input_data>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <user_question>{user_question}</user_question>
</input_data>

### Search Optimization Heuristics:
1. **Target Primary Sources (Trust Anchoring):** You must actively direct the search engine to trusted academic, institutional, and government databases.
2. **Force Raw Data (Avoid Aggregators):** Search aggregators (like ResearchGate or Semantic Scholar) return useless SEO metadata. To bypass them and get actual research data, append `filetype:pdf` or `filetype:xls` when looking for specific metrics or studies.
3. **Domain Anchoring:** Always include explicitly biological keywords (e.g., "sugarcane", "Saccharum") to prevent matching general web noise.
4. **Keyword Density:** Strip all conversational filler ("I would like to know"). Use dense biological nouns, cultivars, and technical metrics.

### Examples of how to respond:
{few_shots}
"""

WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT = PromptTemplate(
    template=WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR,
    input_variables=["conversation_summary", "user_question"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)