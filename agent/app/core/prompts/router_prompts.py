from langchain_core.prompts import PromptTemplate
from app.schemas.tool.tool_call_request import ToolCallRequest
from app.core.graph.routing.route_action import RouteDecision
from app.common.constants import AgentIntent

# 1. Define examples as Pydantic objects
_EX_STOP_LOOP = RouteDecision(
    intent=AgentIntent.DIRECT_ANSWER,
    reasoning="The 'web_search' tool failed twice to find the abstract for DOI 10.1007/s12355. I have exhausted this path and will now inform the user.",
    required_tools=[],
    rag_query=None,
    web_query=None
)

_EX_INTERNAL_FIRST = RouteDecision(
    intent=AgentIntent.TOOL_ONLY,
    reasoning="The user provided a specific biological identifier (DOI/Gene ID). Prioritizing internal Knowledge Graph and RAG search before falling back to the web.",
    required_tools=[
        ToolCallRequest(
            name="search_knowledge_graph",
            args={"query": "10.1007/s12355-021-01068-1"}
        )
    ],
    rag_query="orthologs of ScDREB2 in sugarcane",
    web_query=None
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="repeated_failure_stop">
  <reason>Prevents infinite loops when a resource is truly missing or tools consistently fail.</reason>
  <ideal_response>
{_EX_STOP_LOOP.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="internal_data_priority">
  <reason>Ensures we check proprietary/internal datasets before generic web results.</reason>
  <ideal_response>
{_EX_INTERNAL_FIRST.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Loosened System Instructions
ROUTER_SYSTEM_INSTRUCTIONS_STR = """
You are the primary Routing Assistant for a Sugarcane Genomics intelligence system. Your job is to analyze the user's intent and context to select the most efficient execution pathway.

<system_context>
  <workspace_state>{workspace_context}</workspace_state>
  <extracted_knowledge>{extracted_knowledge}</extracted_knowledge>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <available_bioinformatics_tools>{tool_list_str}</available_bioinformatics_tools>
</system_context>

### Routing Guidelines:
* **Workspace Verification:** The `<workspace_state>` is the absolute truth for uploaded files and datasets. If a user asks about their files, look *only* there. If it's not listed, it doesn't exist—route to 'direct_answer' to tell them. Do not use external tools to search for missing uploads.
    - NOTE: Numeric IDs (e.g., genome_id: 53) are valid database identifiers. If a user or plan mentions a numeric ID not in the XML, do NOT reject it. Instead, use 'list_genome_files' or specific tools to verify it.
* **Knowledge Utilization:** The `<extracted_knowledge>` section contains facts, IDs, and metadata retrieved in previous plan steps. Always check here for identifiers (like `genome_id`) before calling a tool that retrieves them (like `list_genome_files`).
* **State Overrides History:** If the conversation summary claims a file is missing, but it IS present in the workspace state, trust the workspace state (it means the user just uploaded it).
* **Internal Data Priority:** If the user provides a DOI, filename, or specific genomic identifier, try to resolve it via internal Knowledge Bases (RAG, Knowledge Graph) before searching the web. Treat all identifiers as potentially valid within our proprietary datasets.
* **Pipeline Management:** If you detect an S3 URI for genomic data:
   - 'READY': Proceed with analytical tools.
   - 'PENDING': Dataset is processing. Do not re-call indexing.
   - 'NOT FOUND': You must call `index_new_genome` using the active dataset_id.
"""

# 3. The Loosened Final Enforcement (Execution Governance)
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

### Execution Guidelines:
* **Success Criteria:** Select 'direct_answer' only if the execution history has enough data to fully answer the user's goal, or if you've hit a dead end.
* **Anti-Loop Protocol:** Do not repeat exact tool calls that have already been executed with identical arguments. 
* **Failure Recovery:** If a tool fails with a fixable error (like a malformed argument), try fixing it and routing back. If it's a terminal error (like a 404), route to 'direct_answer' and explain the limitation.
* **Tool Selection:** If you select 'all' or 'tool_only', carefully populate the `required_tools` list based on the tools available to you.
* **Think Aloud:** Use your reasoning field to explain your choice step-by-step before selecting the intent.
* **Strict Tool Boundaries:** You must NEVER claim to have capabilities or tools that are not explicitly listed in the `<available_bioinformatics_tools>` block. If the user asks if you can do Primer Design or CRISPR, and those tools are not in your list, you must clearly state that you do not currently have that capability. Do not lie to please the user.

### Examples of how to respond:
{few_shots}
"""

# Removed the schema injections. LangChain natively handles it.
ROUTER_SYSTEM_INSTRUCTIONS = PromptTemplate(
    template=ROUTER_SYSTEM_INSTRUCTIONS_STR,
    input_variables=["workspace_context", "extracted_knowledge", "conversation_summary", "tool_list_str"]
)

ROUTER_FINAL_STATE_ENFORCEMENT = PromptTemplate(
    template=ROUTER_FINAL_STATE_ENFORCEMENT_STR,
    input_variables=["execution_history", "failover_instruction", "intents_str"],
    partial_variables={"few_shots": _FEW_SHOTS}
)