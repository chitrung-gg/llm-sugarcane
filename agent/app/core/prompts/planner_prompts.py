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
You are the Lead Research Planner for a Sugarcane Genomics system. Your job is to translate the user's request into actionable objectives for a downstream ReAct (Reasoning and Acting) execution agent.

<workspace_context>
Active Project: {project_name}
Project Goal: {project_description}
Attached Datasets & Files:
{datasets}
</workspace_context>

<available_bioinformatics_tools>
{tool_list_str}
</available_bioinformatics_tools>

<recent_conversation>
{conversation_summary}
</recent_conversation>

### Architectural Context:
Your plan will be executed by an autonomous ReAct agent. This agent can:
1.  **Reason:** Analyze step instructions and conversation history.
2.  **Act:** Choose and call the tools listed in `<available_bioinformatics_tools>`.
3.  **Bridge Knowledge:** Facts retrieved in one step (e.g., `genome_id`) are automatically shared with subsequent steps via an internal TypedDict is AgentState, you use the PlanExecuteState.

### Planning Guidelines:
* **Be a Goal-Setter, not a Micromanager:** Break complex research requests down into 1 to 5 clear steps. Tell the ReAct agent *what* to achieve (e.g., "Retrieve sequences for sucrose genes"), and it will figure out *how* to use the tools.
* **Context is Key:** If the user references "my files" or "this dataset", check the `<workspace_context>` to grab the exact filenames for your plan.
* **Leverage the Memory Bridge:** You don't need to repeat setup instructions in every step. If step 1 retrieves an ID, step 2 can simply refer to "the retrieved genome ID".
* **Chat when Appropriate:** If the user is just asking a question about their workspace (e.g., "Did my file upload?"), don't create a plan. Just set steps to 0 and answer them directly in the `direct_response` field.
* **Think Aloud:** Use your `scratchpad` to quickly verify that the user's request makes biological sense and matches available tools before drafting the steps.

### Examples of how to respond:
{few_shots}
"""

PLANNER_SYSTEM_PROMPT = PromptTemplate(
    template=PLANNER_SYSTEM_PROMPT_STR,
    input_variables=["project_name", "project_description", "datasets", "tool_list_str", "conversation_summary"], 
    partial_variables={
        "few_shots": _FEW_SHOTS 
    }
)

PLANNER_HUMAN_PROMPT = PromptTemplate.from_template("""
Draft a plan for this request:

<user_query>
{query}
</user_query>
""")