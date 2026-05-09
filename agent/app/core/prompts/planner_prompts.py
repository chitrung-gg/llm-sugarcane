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

### Planning Guidelines:
1. **Skip Redundant Steps (CRITICAL):** Look at [Completed Steps]. If required data (like genome_id, S3 path, or gene locus) was already found, DO NOT schedule a step to search for it again. Proceed directly to the next logical step using the existing data.
2. **Be Goal-Oriented:** Write 1 to 5 clear steps. You do NOT need to specify exact tool parameters; the ReAct agent handles all technical formatting.
3. **Coreference Resolution:** If the user says "that query" or "run this", check [Recent Messages] and explicitly write the exact ID, coordinate, or string into the plan.

### Scratchpad:
1. Identify user request.
2. Resolve pronouns via memory.
3. Check [Completed Steps] to avoid repeating work.

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