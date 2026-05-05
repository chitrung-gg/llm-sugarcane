import json
from langchain_core.prompts import PromptTemplate
from app.schemas.agent.replanner import ReplanOutput
from app.core.graph.state.planner_state import AgentStepPlan

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_REPLAN_OUTPUT_SCHEMA = json.dumps(ReplanOutput.model_json_schema(), indent=2)

# 1. Define examples as Pydantic objects
_EX_CONTINUE = ReplanOutput(
    is_complete=False,
    final_answer="",
    updated_plan=[
        AgentStepPlan(step_id=2, description="Use the literature tool to find the citation count for paper X.")
    ]
)

_EX_COMPLETE = ReplanOutput(
    is_complete=True,
    final_answer="The R570 genome assembly has an N50 of 1.2Mb and contains 85,000 predicted genes, which I have successfully summarized for you.",
    updated_plan=[]
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example_scenario name="partial_progress">
  <scenario>The agent successfully retrieved a requested paper's abstract, but citation counts are still missing.</scenario>
  <ideal_response>
{_EX_CONTINUE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>

<example_scenario name="task_completion">
  <scenario>All requested genomic metrics for R570 have been retrieved and synthesized.</scenario>
  <ideal_response>
{_EX_COMPLETE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

REPLANNER_SYSTEM_PROMPT_STR = """
<role>
You are a Research Manager overseeing an autonomous Bioinformatics Execution Agent.
Your objective is to evaluate the current state of an ongoing workflow, determine if the user's original query has been fully resolved, and issue either a final answer or an updated execution plan.
</role>

<evaluation_rules>
1. COMPLETE SUCCESS: If the completed steps contain sufficient information to fully answer the original query, set 'is_complete' to true and formulate the comprehensive 'final_answer'.
2. PARTIAL FAILURE (PIVOT REQUIRED): If a recent step failed (e.g., "API timeout", "no results found"), DO NOT immediately mark as complete. Evaluate if an alternative strategy or database could yield the data. Set 'is_complete' to false and output an 'updated_plan' with new steps.
3. TOTAL FAILURE (DEAD END): If a step failed AND you have logically exhausted all alternative tools/approaches, set 'is_complete' to true. Provide a 'final_answer' that summarizes what was found and explicitly states what data is permanently missing.
4. CONTINUE NORMAL PLAN: If steps are pending and previous steps succeeded as expected, set 'is_complete' to false and carry over the remaining steps into the 'updated_plan'.
</evaluation_rules>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{replan_output_schema}
</output_directive>
"""

REPLANNER_SYSTEM_PROMPT = PromptTemplate(
    template=REPLANNER_SYSTEM_PROMPT_STR,
    input_variables=[],
    partial_variables={
        "replan_output_schema": _REPLAN_OUTPUT_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)

REPLANNER_HUMAN_PROMPT = PromptTemplate.from_template("""
Please evaluate the current execution state:

<original_query>
{query}
</original_query>

<completed_steps_log>
{completed_text}
</completed_steps_log>

<pending_steps_remaining>
{pending_steps}
</pending_steps_remaining>
""")
