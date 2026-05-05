import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.planner import PlanOutput
from app.core.graph.state.planner_state import AgentStepPlan

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_PLAN_OUTPUT_SCHEMA = json.dumps(PlanOutput.model_json_schema(), indent=2)

# 1. Define examples as Pydantic objects
_EX_ORTHOLOGS = PlanOutput(
    scratchpad="Valid request. Goal: Ortholog identification. User mentioned 'attached genome', which matches 'Sorghum_bicolor.fasta'. Logic: 1. Sequence retrieval -> 2. Local BLAST.",
    direct_response=None,
    estimated_steps=2,
    steps=[
        AgentStepPlan(step_id=1, description="Retrieve the nucleotide sequence for ScDREB2."),
        AgentStepPlan(step_id=2, description="Run a BLAST search using the ScDREB2 sequence against the attached 'Sorghum_bicolor.fasta' reference genome.")
    ]
)

_EX_STATUS_CHECK = PlanOutput(
    scratchpad="User is asking for a workspace status check. No bioinformatics tools needed. Answering directly.",
    direct_response="You currently have 1 dataset attached, containing the file 'Sorghum_bicolor.fasta'.",
    estimated_steps=0,
    steps=[]
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example_scenario name="biological_research">
  <user_query>Find orthologs of ScDREB2 in the attached Sorghum genome.</user_query>
  <ideal_response>
{_EX_ORTHOLOGS.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>

<example_scenario name="status_check">
  <user_query>what files do I have?</user_query>
  <ideal_response>
{_EX_STATUS_CHECK.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

PLANNER_SYSTEM_PROMPT_STR = """
<role>
You are a Senior Bioinformatics Research Planner specialized in Sugarcane Genomics. Your objective is to deconstruct complex user queries into high-level, sequential objectives for a downstream autonomous agent.
</role>

<workspace_context>
Active Project: {project_name}
Project Goal/Description: {project_description}

Available Datasets and Files:
{datasets}
</workspace_context>

<instructions>
1. SANITY CHECK: If the <user_query> is nonsensical or lacks research intent, set 'estimated_steps' to 0 and use 'direct_response' to ask for clarification.
2. DOMAIN FOCUS: Prioritize workflows related to sugarcane cultivars, synteny analysis, genome assemblies, and trait mapping.
3. DATASET AWARENESS: Review the <workspace_context>. Explicitly reference the exact filenames in your step descriptions. If no datasets are attached, state that local file analysis cannot be performed.
4. HIGH-LEVEL OBJECTIVES: Do not micromanage tool calls. Write clear, goal-oriented descriptions for each step. The downstream ReAct agent will figure out which tools to use.
5. CHAIN-OF-THOUGHT: Use the <scratchpad> to verify biological validity and file availability before finalizing the plan.
6. DIRECT QA / STATUS CHECKS: If the user asks a direct question about their workspace (e.g., "What files did I upload?"), read the <workspace_context> and answer them directly in the 'direct_response' field. Set 'estimated_steps' to 0 and leave 'steps' empty.
</instructions>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{plan_output_schema}

Think step-by-step in your scratchpad before finalizing the plan.
</output_directive>
"""

PLANNER_SYSTEM_PROMPT = PromptTemplate(
    template=PLANNER_SYSTEM_PROMPT_STR,
    input_variables=["project_name", "project_description", "datasets"],
    partial_variables={
        "plan_output_schema": _PLAN_OUTPUT_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)

PLANNER_HUMAN_PROMPT = PromptTemplate.from_template("""
Please create an execution plan for the following request:

<user_query>
{query}
</user_query>
""")