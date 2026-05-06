from langchain_core.prompts import PromptTemplate
from app.schemas.agent.rag import OptimizedRagQuery

# 1. Define examples as Pydantic objects
_EX_SYNTENY = OptimizedRagQuery(
    search_query="sugarcane R570 synteny gff3 data rows"
)

_EX_DROUGHT = OptimizedRagQuery(
    search_query="genes drought stress cultivar SP80-3280"
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

# 2. The Loosened System Prompt
RAG_QUERY_OPTIMIZATION_PROMPT_STR = """
You are a Semantic Search Optimizer for a Sugarcane Genomics vector database. Your job is to convert the user's conversational question into a standalone, highly optimized keyword search query.

<conversation_summary>
{conversation_summary}
</conversation_summary>

<user_question>
{user_question}
</user_question>

### Guidelines:
* **Resolve Context:** Replace all pronouns (e.g., "it", "this cultivar", "that file") in the user's question with the specific entity names found in the `<conversation_summary>`.
* **Keyword Density:** Strip out conversational fluff like "Tell me about" or "Can you find". Focus strictly on the core nouns, genes, traits, and actions.
* **Filename Smart-Matching:** If the user refers to an uploaded file, extract the core "human-readable" part of the filename from the summary. Ignore system-generated UUID prefixes (e.g., if a file is `uuid123_R570_assembly.fasta`, just use `R570 assembly fasta`).
* **Conciseness:** Keep the output highly relevant and avoid unnecessary repetition.

### Examples of how to respond:
{few_shots}
"""

# Removed the schema injection entirely; LangChain handles it natively.
RAG_QUERY_OPTIMIZATION_PROMPT = PromptTemplate(
    template=RAG_QUERY_OPTIMIZATION_PROMPT_STR,
    input_variables=["conversation_summary", "user_question"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)