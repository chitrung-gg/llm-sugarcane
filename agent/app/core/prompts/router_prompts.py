import json
from langchain_core.prompts import PromptTemplate
from app.schemas.tool.tool_call_request import ToolCallRequest
from app.core.graph.routing.route_action import RouteDecision
from app.common.constants import AgentIntent

# 1. Define heuristic examples as Pydantic objects
_EX_PIVOT_ON_FAILURE = RouteDecision(
    intent=AgentIntent.WEB_SEARCH, 
    reasoning="The 'search_knowledge_graph' tool failed to find 'ZZ1' in the execution history. I MUST pivot to a different capability. I will use 'web_search' to find broader external literature.",
    required_tools=[],
    rag_query=None,
    web_query="sugarcane ZZ1 genome assembly traits"
)

_EX_RAG_FIRST = RouteDecision(
    intent=AgentIntent.RAG_ONLY,
    reasoning="The task requires finding information about a specific sugarcane trait. According to my heuristics, I must prioritize 'rag_only' to search the high-fidelity internal documents before attempting to use the secondary Knowledge Graph.",
    required_tools=[],
    rag_query="Sugarcane drought resistance traits and associated genes",
    web_query=None
)

_EX_META_ROUTER = RouteDecision(
    intent=AgentIntent.DIRECT_ANSWER, 
    reasoning="The task asks to read sources for a previous answer. The <extracted_knowledge> and <conversation_summary> already contain this information. I do not need external tools or RAG; I will answer directly.",
    required_tools=[],
    rag_query=None,
    web_query=None
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="heuristic_pivot_on_failure">
  <reason>Shows how to adapt when an internal tool fails, preventing infinite loops by pivoting to a different capability (Web Search).</reason>
  <ideal_response>
{_EX_PIVOT_ON_FAILURE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="heuristic_internal_priority">
  <reason>Shows capability-based routing for exact biological identifiers.</reason>
  <ideal_response>
{_EX_RAG_FIRST.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="heuristic_meta_question">
  <reason>Shows how to resolve tasks natively if the context already holds the answer.</reason>
  <ideal_response>
{_EX_META_ROUTER.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Capabilities-Driven System Instructions
ROUTER_SYSTEM_INSTRUCTIONS_STR = """
You are the Execution Router for a Sugarcane Genomics intelligence system. Your job is to analyze the current task and select the most efficient capability (`intent`) to solve it.

<system_context>
  <workspace_state>{workspace_context}</workspace_state>
  <extracted_knowledge>{extracted_knowledge}</extracted_knowledge>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <available_bioinformatics_tools>{tool_list_str}</available_bioinformatics_tools>
</system_context>

### Intent Selection Heuristics (Capabilities Map):
- **`direct_answer` (Resolution):** FASTEST. Use this if the `<extracted_knowledge>`, `<workspace_state>`, or `<conversation_summary>` ALREADY contains the exact answer needed.
- **`rag_only` (Primary Internal Memory):** PRIORITY SEARCH. Always prefer this FIRST when looking up biological context, trait data, or literature. It queries high-fidelity vector databases.
- **`tool_only` / `all` (Secondary Structured Bioinformatics):** SECONDARY. Use this (e.g., Knowledge Graph, NCBI APIs) ONLY IF `rag_only` previously failed, or if the task explicitly requires querying an external API with an exact identifier (DOIs, Accessions).
- **`web_search` (Broad Discovery):** FALLBACK. Use this for general scientific literature searches, recent news, or if internal tools/databases explicitly failed.
"""

# 3. The Heuristic-Driven Final Enforcement
ROUTER_FINAL_STATE_ENFORCEMENT_STR = """
<execution_history>
{execution_history}
</execution_history>

<failover_instruction>
{failover_instruction}
</failover_instruction>

<available_intents>
{intents_str}
</available_intents>

### Execution & Self-Correction Guidelines:
1. **RAG-First Priority:** Unless the user explicitly asks to run a specific computational pipeline, always route to `rag_only` before attempting to use the `search_knowledge_graph` tool.
2. **Argument Precision (No Guessing):** If you choose `tool_only` or `all`, you MUST pull the exact IDs, DOIs, or Accession numbers from the `<extracted_knowledge>` or `<conversation_summary>`. Do not invent parameters.
3. **Learn from History (Anti-Loop):** Read the `<execution_history>`. If a specific intent (like `rag_only`) failed to find data, YOU MUST PIVOT to a new capability (like `tool_only` or `web_search`). Do not repeat the exact same search.
4. **Trust the State:** The `<workspace_state>` represents ground truth for user files. Do not use external tools to look for local user uploads.
5. **Think Aloud:** Use your `reasoning` field to explicitly state *why* you chose this intent based on your Capabilities Map.

### Examples of how to respond:
{few_shots}
"""

ROUTER_SYSTEM_INSTRUCTIONS = PromptTemplate(
    template=ROUTER_SYSTEM_INSTRUCTIONS_STR,
    input_variables=["workspace_context", "extracted_knowledge", "conversation_summary", "tool_list_str"]
)

ROUTER_FINAL_STATE_ENFORCEMENT = PromptTemplate(
    template=ROUTER_FINAL_STATE_ENFORCEMENT_STR,
    input_variables=["execution_history", "failover_instruction", "intents_str"],
    partial_variables={"few_shots": _FEW_SHOTS}
)