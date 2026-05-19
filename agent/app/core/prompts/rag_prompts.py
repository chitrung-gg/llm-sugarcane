from langchain_core.prompts import PromptTemplate
from app.schemas.agent.rag import OptimizedRagQuery

# 1. Define examples as Pydantic objects
_EX_SYNTENY = OptimizedRagQuery(
  search_query="sugarcane R570 synteny gff3 data rows"
)

_EX_DROUGHT = OptimizedRagQuery(
  search_query="genes drought stress tolerance water deficit cultivar SP80-3280"
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="file_specific_query">
  <conversation_summary>User uploaded '9b1deb4d-3b7d_sugarcane_R570_synteny.gff3'.</conversation_summary>
  <user_question>What are the first 10 rows of that synteny file?</user_question>
  <ideal_response>
{_EX_SYNTENY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="biological_context">
  <conversation_summary>User is asking about cultivar SP80-3280.</conversation_summary>
  <user_question>What genes are related to drought stress in it?</user_question>
  <ideal_response>
{_EX_DROUGHT.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Heuristic-Driven System Prompt
RAG_QUERY_OPTIMIZATION_PROMPT_STR = """
You are the Semantic Search Architect for a Sugarcane Genomics Vector Database (Qdrant). Your objective is to translate a conversational user query into a highly dense, embedding-friendly search string.

<input_data>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <user_question>{user_question}</user_question>
</input_data>

### Vector Search Optimization Heuristics:
1. **Entity Resolution (Context is King):** Vector embedding models cannot resolve pronouns ("it", "this cultivar", "that file"). You MUST replace all pronouns in the `<user_question>` with the explicit biological entities (e.g., "R570", "ScDREB2") found in the `<conversation_summary>`.
2. **Embedding Density:** Vector databases match on semantic meaning, not conversational syntax. Strip out all conversational fluff ("Tell me about", "What is", "Can you find"). Retain ONLY the core nouns, genes, traits, and scientific actions.
3. **No Boolean Operators:** Do not use "AND", "OR", or "NOT". Vector models do not process boolean logic well; they map coordinates. Just list the highly relevant keywords.
4. **Filename Smart-Matching:** If the user refers to an uploaded document, extract only the human-readable core of the filename. Drop system UUID prefixes (e.g., convert `9b1deb4d_R570_assembly.fasta` -> `R570 assembly fasta`).

### Examples of how to respond:
{few_shots}
"""

# Schema injection removed entirely; LangChain handles it natively.
RAG_QUERY_OPTIMIZATION_PROMPT = PromptTemplate(
    template=RAG_QUERY_OPTIMIZATION_PROMPT_STR,
    input_variables=["conversation_summary", "user_question"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)