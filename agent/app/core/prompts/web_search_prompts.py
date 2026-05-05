import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.web_search import OptimizedSearchQuery

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_WEB_SEARCH_OPTIMIZATION_SCHEMA = json.dumps(OptimizedSearchQuery.model_json_schema(), indent=2)

# 1. Define examples as Pydantic objects 
_EX_METABOLIC = OptimizedSearchQuery(
    search_query="SP80-3280 sugarcane Saccharum metabolic response drought stress research papers 2024..2026"
)

_EX_COMPARATIVE = OptimizedSearchQuery(
    search_query="Saccharum hybrid R570 vs Sorghum bicolor genome comparative synteny analysis"
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example_scenario name="metabolic_research">
  <conversation_summary>Discussing drought resistance in sugarcane cultivar SP80-3280.</conversation_summary>
  <user_question>Find more recent papers on its metabolic response.</user_question>
  <ideal_response>
{_EX_METABOLIC.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>

<example_scenario name="comparative_genomics">
  <conversation_summary>User is researching the R570 genome assembly.</conversation_summary>
  <user_question>Are there any studies comparing it to the sorghum genome?</user_question>
  <ideal_response>
{_EX_COMPARATIVE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR = """
<role>
You are an expert Search Query Optimizer for Bioinformatics and Genomic Research.
Your objective is to transform conversational user input into a precise, keyword-dense search engine query optimized for academic and technical retrieval.
</role>

<context>
  <conversation_summary>{conversation_summary}</conversation_summary>
</context>

<optimization_rules>
1. ENTITY RESOLUTION: Replace all ambiguous pronouns (e.g., "this gene", "that paper", "the variety") with explicit identifiers found in the <conversation_summary>.
2. SPECIES ANCHORING: If the context involves sugarcane, ensure terms like "Saccharum officinarum" or "Saccharum spontaneum" are included to filter out irrelevant plant results.
3. NO CONVERSATIONAL FILLER: Strip all phrases like "I would like to know", "Search for", or "What does the literature say about".
4. KEYWORD DENSITY: Prioritize biological nouns, cultivar names, and technical metrics (e.g., "synteny", "polyploidy", "QTL mapping").
</optimization_rules>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{web_search_optimization_schema}
</output_directive>
"""

WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT = PromptTemplate(
    template=WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT_STR,
    input_variables=["conversation_summary"],
    partial_variables={
        "web_search_optimization_schema": _WEB_SEARCH_OPTIMIZATION_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)
