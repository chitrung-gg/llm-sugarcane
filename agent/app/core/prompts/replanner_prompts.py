from langchain_core.prompts import PromptTemplate
from app.schemas.agent.replanner import ReplanOutput
from app.core.graph.state.planner_state import AgentStepPlan

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

# 2. Add back the exclusion rules to hide internal state (status, error_message)
_JSON_OPTS = {
    "indent": 2, 
    "exclude_none": True,
    "exclude": {"updated_plan": {"__all__": {"status", "error_message", "retry_count"}}}
}

_FEW_SHOTS = f"""
<example name="partial_progress">
  <scenario>The agent successfully retrieved a requested paper's abstract, but citation counts are still missing.</scenario>
  <ideal_response>
{_EX_CONTINUE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="task_completion">
  <scenario>All requested genomic metrics for R570 have been retrieved and synthesized.</scenario>
  <ideal_response>
{_EX_COMPLETE.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# 3. The Loosened System Prompt
REPLANNER_SYSTEM_PROMPT_STR = """
You are the Research Manager overseeing an autonomous Bioinformatics Execution Agent. Your job is to evaluate the current state of an ongoing workflow, determine if the user's original query has been fully resolved, and issue either a final answer or an updated execution plan.

### Guidelines:
* **Complete Success:** If the completed steps contain enough information to fully answer the original query, set `is_complete` to true and write a comprehensive `final_answer`.
* **Pivot on Failure:** If a recent step failed (e.g., API timeout, no results), do not immediately mark as complete. Evaluate if an alternative strategy or tool could yield the data. If so, set `is_complete` to false and output an `updated_plan` with new steps.
* **Dead Ends:** If a step failed and you have logically exhausted all alternative approaches, set `is_complete` to true. Provide a `final_answer` that summarizes what was found and explicitly states what data is permanently missing.
* **Continue as Planned:** If steps are still pending and previous steps succeeded as expected, set `is_complete` to false and carry over the remaining steps into the `updated_plan`.

### Examples of how to respond:
{few_shots}
"""

# Schema injection removed entirely
REPLANNER_SYSTEM_PROMPT = PromptTemplate(
    template=REPLANNER_SYSTEM_PROMPT_STR,
    input_variables=[],
    partial_variables={
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