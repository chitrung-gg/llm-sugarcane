import json
from langchain_core.prompts import PromptTemplate
from app.schemas.tool.tool_call_request import ToolCallRequest
from app.core.graph.routing.route_action import RouteDecision
from app.common.constants import AgentIntent

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_ROUTE_DECISION_SCHEMA = json.dumps(RouteDecision.model_json_schema(), indent=2)

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
<example_scenario name="repeated_failure_stop">
  <reason>Prevents infinite loops when a resource is truly missing or tools consistently fail.</reason>
  <ideal_response>
{_EX_STOP_LOOP.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>

<example_scenario name="internal_data_priority">
  <reason>Ensures we check proprietary/internal datasets before generic web results.</reason>
  <ideal_response>
{_EX_INTERNAL_FIRST.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

ROUTER_SYSTEM_INSTRUCTIONS_STR = """
<role>
You are an expert routing assistant for the Sugarcane Genomics intelligence system.
Your objective is to analyze the user's intent and context to select the most efficient execution pathway.
</role>

<system_context>
  <workspace_state>{workspace_context}</workspace_state>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <available_bioinformatics_tools>{tool_list_str}</available_bioinformatics_tools>
</system_context>

<routing_logic_rules>
  <rule_set name="workspace_verification">
    1. ABSOLUTE TRUTH: The <workspace_state> block contains the complete and final list of all files uploaded by the user. 
    2. FILE QUERIES: If a user asks "Did I upload X?" or "Where is my file?", you MUST look ONLY at the <workspace_state>. 
    3. DO NOT GUESS: If the file is not listed in <workspace_state>, it does not exist in their workspace. Select the 'direct_answer' intent immediately and inform them it is missing. DO NOT attempt to use external backend tools to search for missing user uploads.
  </rule_set>
                                                          
  <rule_set name="internal_data_priority">
    1. PRIORITIZE INTERNAL DATA: If the user provides a DOI, filename, or specific genomic identifier, you MUST attempt to resolve it via internal Knowledge Bases (RAG, Knowledge Graph, ...) before searching the web.
    2. FUTURE IDENTIFIERS: Treat all identifiers as potentially valid within our proprietary datasets.
  </rule_set>

  <rule_set name="bioinformatics_pipeline_management">
    1. S3 URI DETECTION: If the workspace or uploaded context contains an S3 URI for genomic data, follow the state machine:
       - If 'READY': Proceed with analytical tools.
       - If 'PENDING': Dataset is processing. DO NOT re-call indexing.
       - If 'NOT FOUND': You MUST call `index_new_genome` using the active dataset_id.
    2. RE-INDEXING: Only call indexing for 'NOT FOUND' or explicit user requests.
  </rule_set>
</routing_logic_rules>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{route_decision_schema}

Think step-by-step in your reasoning before outputting the selected intent. Ensure all required tool arguments are mapped from the <system_context>.
</output_directive>
"""

ROUTER_FINAL_STATE_ENFORCEMENT_STR = """
<execution_governance>
  <execution_history>
  {execution_history}
  </execution_history>

  <failover_instruction>
  {failover_instruction}
  </failover_instruction>

  <strict_runtime_rules>
    1. SUCCESS CRITERIA: Select 'direct_answer' only if the <execution_history> provides sufficient data to fully resolve the user's goal.
    2. ANTI-LOOP PROTOCOL: If the history shows a tool was "ALREADY EXECUTED" with identical arguments, you are FORBIDDEN from calling it again.
    3. TOOL FAILURE RECOVERY: Upon tool failure:
       - If the error is fixable (e.g., malformed argument), retry ONCE with corrected parameters.
       - If the error is terminal (e.g., 404, Resource Missing), select 'direct_answer' and explain the limitation.
    4. TOOL POPULATION: If 'all' or 'tool_only' is selected, you MUST populate the `required_tools` list based on the <available_intents>.
  </strict_runtime_rules>
</execution_governance>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<available_intents>
{intents_str}
</available_intents>

<final_enforcement>
Reminder: Your output must match the RouteDecision schema exactly.
</final_enforcement>
"""

ROUTER_SYSTEM_INSTRUCTIONS = PromptTemplate(
    template=ROUTER_SYSTEM_INSTRUCTIONS_STR,
    input_variables=["workspace_context", "conversation_summary", "tool_list_str"],
    partial_variables={"route_decision_schema": _ROUTE_DECISION_SCHEMA}
)

ROUTER_FINAL_STATE_ENFORCEMENT = PromptTemplate(
    template=ROUTER_FINAL_STATE_ENFORCEMENT_STR,
    input_variables=["execution_history", "failover_instruction", "intents_str"],
    partial_variables={"few_shots": _FEW_SHOTS}
)