import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.rag import OptimizedRagQuery

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_RAG_OPTIMIZATION_SCHEMA = json.dumps(OptimizedRagQuery.model_json_schema(), indent=2)

# 1. Define examples as Pydantic objects (IDE-tracked, no hardcoded strings)
_EX_SYNTENY = OptimizedRagQuery(
    search_query="sugarcane R570 synteny gff3 data rows"
)

_EX_DROUGHT = OptimizedRagQuery(
    search_query="genes drought stress cultivar SP80-3280"
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example_scenario name="file_specific_query">
  <conversation_summary>User uploaded '9b1deb4d-3b7d_sugarcane_R570_synteny.gff3'.</conversation_summary>
  <user_question>What are the first 10 rows of that synteny file?</user_question>
  <ideal_response>
{_EX_SYNTENY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>

<example_scenario name="biological_context">
  <conversation_summary>User is asking about cultivar SP80-3280.</conversation_summary>
  <user_question>What genes are related to drought stress in it?</user_question>
  <ideal_response>
{_EX_DROUGHT.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

RAG_QUERY_OPTIMIZATION_PROMPT = PromptTemplate(
    template="""
<role>
You are a Semantic Search Optimizer for a Sugarcane Genomics vector database.
Your objective is to convert the user's conversational question into a standalone, highly optimized search query.
</role>

<context>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <user_question>{user_question}</user_question>
</context>

<rules>
1. RESOLVE CONTEXT: Replace all pronouns (e.g., "it", "this cultivar") with specific entity names from the <conversation_summary>.
2. BE CONCISE: Maximize information density. Limit the output to 10-15 highly relevant terms. 
3. REMOVE FLUFF: Strip conversational filler (e.g., "Tell me about").
4. NO REPETITION: Do not repeat words.
5. FILENAME PARTIAL MATCHING: If the user refers to an uploaded file, extract the core "human-readable" part of the filename. Ignore system-generated UUID prefixes (e.g., if a file is 'uuid123_R570_assembly.fasta', use 'R570 assembly').
</rules>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{rag_optimization_schema}
</output_directive>
""",
    input_variables=["conversation_summary", "user_question"],
    partial_variables={
        "rag_optimization_schema": _RAG_OPTIMIZATION_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)