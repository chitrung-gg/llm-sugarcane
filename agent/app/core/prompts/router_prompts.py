import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.router import RouteDecision
from app.schemas.tool.tool_call_request import ToolCallRequest
from app.common.constants import AgentIntent

_EX_NCBI_PRIORITY = RouteDecision(
    intent=AgentIntent.TOOL_ONLY,
    reasoning="The user asks for the N50 statistic of the 'Arabidopsis thaliana' genome. The <workspace_state> and <conversation_summary> show this genome is NOT part of our internal system. Following the Local vs. NCBI Boundary rule, I MUST route this to external NCBI tools.",
    required_tools=[ToolCallRequest(name="ncbi_genome_fetch", args={"organism": "Arabidopsis thaliana", "data_type": "statistics"})],
    rag_query=None,
    web_query=None
)

_EX_LOCAL_PRIORITY = RouteDecision(
    intent=AgentIntent.TOOL_ONLY,
    reasoning="The user asks for the N50 and structural features of the R570 genome. The <workspace_state> shows R570 is an active internal sugarcane genome. Following the Local vs. NCBI Boundary rule, I MUST use our internal 'get_genome_analysis' tool.",
    required_tools=[ToolCallRequest(name="get_genome_analysis", args={"id": 1, "force_refresh": False})], 
    rag_query=None,
    web_query=None
)

_EX_RAG_FIRST = RouteDecision(
    intent=AgentIntent.RAG_ONLY,
    reasoning="The step asks for a methodology (NWSB determination) from the file 'bioinformatics.pdf'. I am extracting the file_id '9b1deb4d-3b7d-4e9b-813a-c5ea6fd19549' from the workspace context and writing a Hybrid-optimized query.",
    required_tools=[],
    rag_query="Methodology for determining non-water-stressed baselines NWSB using canopy temperature Tc-Ta and vapor pressure deficit VPD",
    web_query=None
)

_EX_PIVOT_ON_FAILURE = RouteDecision(
    intent=AgentIntent.WEB_SEARCH, 
    reasoning="The internal RAG and knowledge graph tools returned 0 results for 'ZZ1'. I MUST pivot to external 'web_search'. I am using the filename 'ZZ1_genome.pdf' as a search keyword for the web.",
    required_tools=[],
    rag_query=None,
    web_query="sugarcane ZZ1 genome assembly traits ZZ1_genome.pdf filetype:pdf"
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="ncbi_priority_external_genome">
  <reason>Shows how to prioritize NCBI tools when the queried genome is NOT in the internal system context.</reason>
  <ideal_response>
{_EX_NCBI_PRIORITY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="local_priority_internal_context">
  <reason>Shows how to prioritize Local APIs (like get_genome_analysis or search_genes_full) when the query targets an internal system genome.</reason>
  <ideal_response>
{_EX_LOCAL_PRIORITY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="heuristic_methodology_hybrid_rag">
  <reason>Shows how to prioritize RAG for methodologies/concepts and format a Hybrid-optimized rag_query.</reason>
  <ideal_response>
{_EX_RAG_FIRST.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="heuristic_pivot_on_failure">
  <reason>Shows how to adapt to Web Search (External) ONLY when internal tools fail, applying strict operators.</reason>
  <ideal_response>
{_EX_PIVOT_ON_FAILURE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 2. The Capabilities-Driven System Instructions
ROUTER_SYSTEM_INSTRUCTIONS_STR = """
You are the Execution Router for a Sugarcane Bioinformatics intelligence system. Your job is to analyze the current task, select the most efficient capability, and generate highly optimized search queries.

<system_context>
  <workspace_state>{workspace_context}</workspace_state>
  <extracted_knowledge>{extracted_knowledge}</extracted_knowledge>
  <conversation_summary>{conversation_summary}</conversation_summary>
  <available_bioinformatics_tools>{tool_list_str}</available_bioinformatics_tools>
</system_context>

### Intent Selection Heuristics (Capabilities Map):
- **`direct_answer`:** Use if the `<extracted_knowledge>` or `<conversation_summary>` ALREADY contains the exact answer. 
- **`rag_only`:** REQUIRED for methodologies, theories, processes, or unstructured text. Use to search internal scientific literature.
- **`tool_only`:** PRECISE. Use ONLY when resolving specific biological identifiers or retrieving exact genome/gene data via Tools (we have a tool Knowledge Graph, but this only get the entity and its relationship represented as a graph, it only used to help the RAG.
- **`all` (Synergy):** Use to run multiple sources (RAG, Web, Tools) concurrently. You MUST provide the corresponding 'rag_query', 'web_query', or 'required_tools' for each source you want to activate.
- **`web_search`:** EXTERNAL FALLBACK. Use for general internet searches ONLY if the user explicitly asks for external data OR if internal databases/tools failed in the history.
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

### Execution & Query Optimization Guidelines (CRITICAL):

1. **The RAG Baseline (For Literature & Concepts):** If the query asks for methodologies, theories, or general scientific concepts, YOU MUST prioritize `rag_only` FIRST to check internal literature. Only use `web_search` if RAG explicitly failed in the <execution_history>.
2. **Local vs. NCBI Boundary (For Genomic Data ONLY):** This rule ONLY applies when extracting specific genome/gene features (N50, sequences, structures). 
   - If the user asks about an internal genome/cultivar, use Local APIs. 
   - If the user asks about a general/external genome (Human, Mouse, etc.), use NCBI tools.
3. **`rag_query` Optimization (POSITIVE SELECTION):** Our database uses Hybrid Search. Your query MUST be a minimalist semantic string consisting ONLY of proper nouns, biological entities, and specific scientific processes.
   - **FORBIDDEN (Analytical Bloat):** Do NOT include words that describe the user's intent or the "status" of the information. These ruin Vector math.
   - **BLOATED:** "current usage status and citation trends of Tuxedo Suite TopHat Cufflinks bioinformatics pipeline active vs deprecated"
   - **OPTIMIZED:** "Tuxedo Suite TopHat Cufflinks transcriptomics read mapping assembly"
   - **BLOATED:** "latest research on ScYLV virus resistance genes in sugarcane cultivars"
   - **OPTIMIZED:** "ScYLV virus resistance genes sugarcane cultivars"
   - **STRICT FILENAME PRESERVATION:** If the user refers to a specific filename from the active datasets, you MUST preserve it exactly as it appears.
   - **INTERNAL RAG IDENTITY (UUID):** For `rag_query` and `all` intents, you MUST extract the corresponding `file_id` (UUID) from the `<workspace_state>` for any document mentioned. Do NOT use the filename in the `rag_query`; use the `file_ids` field for strict metadata filtering. and when return, use that UUID.
5. **Anti-Loop (Query Relaxation):** If the `<execution_history>` shows that your previous query failed, DO NOT repeat the same keywords. Relax the query to search only for the core concept to broaden the recall.
6. **Think Aloud:** Use your `reasoning` field to explicitly state *why* you chose the intent based on these rules.

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