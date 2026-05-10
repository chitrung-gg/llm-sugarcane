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

_EX_INTERNAL_FIRST = RouteDecision(
    intent=AgentIntent.TOOL_ONLY,
    reasoning="The task requires resolving a specific biological identifier (DOI 10.1007/s12355). Based on my capabilities map, I will prioritize internal structured tools before falling back to the web.",
    required_tools=[
        ToolCallRequest(
            name="search_knowledge_graph",
            args={"query": "10.1007/s12355"}
        )
    ],
    rag_query=None,
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
{_EX_INTERNAL_FIRST.model_dump_json(**_JSON_OPTS)}
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
- **`direct_answer` (Resolution):** FASTEST. Use this if the `<extracted_knowledge>`, `<workspace_state>`, or `<conversation_summary>` ALREADY contains the exact answer needed. Also use this for simple conversational pleasantries or meta-questions ("What files do I have?").
- **`rag_only` (Unstructured Internal Memory):** Use this to search vector databases for unstructured text inside user-uploaded PDFs, FASTA descriptions, or general biological context. 
- **`tool_only` / `all` (Structured Bioinformatics):** PRECISE. Use this when the task explicitly requires APIs (NCBI, SCOD) or Knowledge Graphs (Neo4j) to resolve exact identifiers (Genes, DOIs, Accessions) or trigger pipelines (e.g., Crispor).
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
1. **Argument Precision (No Guessing):** If you choose `tool_only` or `all`, you MUST pull the exact IDs, DOIs, or Accession numbers from the `<extracted_knowledge>` or `<conversation_summary>` to populate your tool `args`. Do not invent or guess parameters.
2. **Learn from History (Anti-Loop):** Read the `<execution_history>`. If a specific intent or tool failed (e.g., "not found", "timeout", "empty"), YOU MUST PIVOT. Do not repeat the exact same tool with the same arguments. Switch capabilities entirely (e.g., from `tool_only` to `web_search`).
3. **Trust the State:** The `<workspace_state>` represents ground truth for user files. If a file is there, it exists. If it is not there, it does not exist. Do not use external tools to look for local user uploads.
4. **Think Aloud:** Use your `reasoning` field to explicitly state *why* you chose this intent based on your Capabilities Map.

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