import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.planner import PlanOutput
from app.core.graph.state.planner_state import AgentStepPlan

# 1. Define examples as Pydantic objects
_EX_ORTHOLOGS = PlanOutput(
    scratchpad="User wants to find orthologs. They mentioned an attached genome, matching 'Sorghum_bicolor.fasta' in the workspace. I'll set up two high-level steps for the ReAct agent.",
    direct_response=None,
    estimated_steps=2,
    steps=[
        AgentStepPlan(step_id=1, description="Retrieve the nucleotide sequence for ScDREB2."),
        AgentStepPlan(step_id=2, description="Run a BLAST search using the ScDREB2 sequence against the attached 'Sorghum_bicolor.fasta' reference genome.")
    ]
)

_EX_STATUS_CHECK = PlanOutput(
    scratchpad="User is just asking what files they have. No research steps are needed. I'll read the workspace context and answer directly.",
    direct_response="You currently have 1 dataset attached, containing the file 'Sorghum_bicolor.fasta'.",
    estimated_steps=0,
    steps=[]
)

_EX_META = PlanOutput(
    scratchpad="User is asking for the sources/papers used to generate the previous answer. Based on the planning philosophy, I must NOT search external APIs. I will plan a single step to review our internal memory and RAG context.",
    direct_response=None,
    estimated_steps=1,
    steps=[
        AgentStepPlan(step_id=1, description="Review the previous execution history and RAG context to extract the exact document names, DOIs, and citations used to formulate the previous answer.")
    ]
)

# 2. Keep exclusion rules to hide internal state from the LLM
_JSON_OPTS = {
    "indent": 2, 
    "exclude_none": True,
    "exclude": {"steps": {"__all__": {"status", "error_message", "retry_count"}}}
}

_FEW_SHOTS = f"""
<example name="standard_research">
  <user_query>Find orthologs of ScDREB2 in the attached Sorghum genome.</user_query>
  <ideal_response>
{_EX_ORTHOLOGS.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="direct_question">
  <user_query>what files do I have?</user_query>
  <ideal_response>
{_EX_STATUS_CHECK.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 3. The Loosened, Goal-Oriented Prompt
PLANNER_SYSTEM_PROMPT_STR = """
You are the Lead Research Planner for a Sugarcane Genomics system. Translate the user's request into actionable objectives for a downstream ReAct agent.

<context>
[Project] 
Name: {project_name}
Description: {project_description}
[Files] {datasets}
[Agent Capabilities]
{agent_capabilities_str}
</context>

<memory>
[Conversation Summary] {conv_summary}
[Recent Messages] {chat_history_str}
[Completed Steps] 
{past_steps_str}
</memory>

### Infrastructure Resource Map (How to solve problems):
Understand the strengths of your available resources to plan efficiently:
1. **Internal RAG / Memory (Fastest, Local):** Best for retrieving data from user-uploaded files, querying the chat history, or finding citations/sources for things we just discussed.
2. **Knowledge Graph (Fast, Relational):** Best for finding entity relationships (e.g., "Which genes are linked to Smut resistance?").
3. **Bioinformatics APIs - NCBI/SCOD (Slow, Precise):** Best when you have an EXACT identifier (Gene Symbol, DOI, Accession) and need highly structured biological metadata.
4. **Web Search (Fallback, Broad):** Best for broad scientific literature searches, recent news, or concepts not found in our internal databases.

### Planning Philosophy & Guidelines:
1. **Start Local, Go Global:** Always plan to check internal workspace files, RAG, or Graph databases before planning external API/Web searches.
2. **Step Dependency (The Linkage Rule):** If a later step depends on the output of an earlier step (e.g., Step 2 needs a Gene ID found in Step 1), explicitly state this dependency in the step description. (Example: "Using the Gene ID extracted in Step 1, query the NCBI database...").
3. **Handling Meta-Questions (Citations/Sources):** If the user asks about the AI's reasoning or sources (e.g., "How do you know?"), plan a SINGLE step to review internal RAG and Conversation History. DO NOT plan external searches.
4. **Skip Redundant Steps:** Look at [Completed Steps]. If required data (like genome_id or S3 path) was already found, DO NOT schedule a step to search for it again. 
5. **Coreference Resolution:** If the user says "that query" or "run this", explicitly write the exact ID, coordinate, or string from [Recent Messages] into the plan.

### Scratchpad Logic:
1. Identify the core user request.
2. Resolve pronouns via memory.
3. Map the request to the correct Infrastructure Resource.
4. Draft the leanest possible plan.

### Examples:
{few_shots}
"""

# 4. Update the PromptTemplate to accept the new input variables
PLANNER_SYSTEM_PROMPT = PromptTemplate(
    template=PLANNER_SYSTEM_PROMPT_STR,
    input_variables=[
        "project_name", 
        "project_description", 
        "datasets", 
        "agent_capabilities_str", 
        "chat_history_str",
        "conv_summary", 
        "past_steps_str"
    ], 
    partial_variables={"few_shots": _FEW_SHOTS}
)

PLANNER_HUMAN_PROMPT = PromptTemplate.from_template("""
Draft a plan for this request:

<user_query>
{query}
</user_query>
""")