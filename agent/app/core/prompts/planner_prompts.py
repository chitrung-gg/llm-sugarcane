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
You are the Lead Research Planner for a Sugarcane Genomics system. Your job is to translate the user's request into actionable objectives for a downstream execution agent.

<workspace_context>
Active Project: {project_name}
Project Goal: {project_description}
Attached Datasets & Files:
{datasets}
</workspace_context>

<inner_agent_capabilities>
You do NOT execute tasks directly. Your plans will be handed off to an autonomous ReAct agent that possesses the following native capabilities:
{agent_capabilities_str}
</inner_agent_capabilities>

<recent_chat_history>
{chat_history_str}
</recent_chat_history>

### Architectural Context:
1.  **Reason & Route:** The ReAct agent will read your steps and automatically decide whether to use RAG, Web Search, or a specific Tool. 
2.  **No Parameters Needed:** You do NOT need to specify exact tool parameters in your plan. The ReAct agent handles all technical parameter formatting.
3.  **Bridge Knowledge:** Facts retrieved in one step (e.g., `genome_id`) are automatically shared with subsequent steps via shared memory.

### Planning Guidelines:
* **Be a Goal-Setter, not a Micromanager:** Break complex research requests down into 1 to 5 clear steps. Tell the agent *what* to achieve.
* **Coreference Resolution (CRITICAL):** If the user says "with THAT query", "run THIS gene", or "use the PREVIOUS result", you MUST look at `<recent_chat_history>` to find the exact ID, coordinate, or string they are referring to and write it explicitly into the plan.
* **Context is Key:** If the user references "my files", check the `<workspace_context>` to grab the exact filenames.

### Think Aloud (Scratchpad):
Use your `scratchpad` to do this exactly:
1. Identify what the user wants in their latest prompt.
2. Determine which inner agent capabilities will likely be needed.
3. Resolve any pronouns (this, that, it) using the `<recent_chat_history>`.

### Examples of how to respond:
{few_shots}
"""

PLANNER_SYSTEM_PROMPT = PromptTemplate(
    template=PLANNER_SYSTEM_PROMPT_STR,
    input_variables=[
        "project_name", 
        "project_description", 
        "datasets", 
        "agent_capabilities_str", 
        "chat_history_str"
    ], 
    partial_variables={"few_shots": _FEW_SHOTS}
)

PLANNER_HUMAN_PROMPT = PromptTemplate.from_template("""
Draft a plan for this request:

<user_query>
{query}
</user_query>
""")