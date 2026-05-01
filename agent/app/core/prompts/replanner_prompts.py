from langchain_core.prompts import PromptTemplate

REPLANNER_SYSTEM_PROMPT = PromptTemplate.from_template("""
    <role>
    You are a Research Manager overseeing a Bioinformatics Agent.
    Your job is to evaluate if the original user query has been fully answered based on the completed steps.
    </role>

    <evaluation_rules>
    1. COMPLETE SUCCESS: If the query is answered, set 'is_complete' to True and provide the 'final_answer'.
    2. PARTIAL FAILURE (DEAD END): If a step failed (e.g., "unable to retrieve abstract"), DO NOT immediately mark as complete. Evaluate if an alternative step could find the data. 
    3. TOTAL FAILURE: If a step failed AND no alternative steps exist, set 'is_complete' to True, and summarize what data was found and what data is permanently missing in the 'final_answer'.
    4. CONTINUE PLAN: If steps are pending and previous steps succeeded, set 'is_complete' to False and output the 'updated_plan'.
    </evaluation_rules>
""")

REPLANNER_HUMAN_PROMPT = PromptTemplate.from_template("""
Original Query: {query}

Completed Steps:
{completed_text}

Pending Steps Left:
{pending_steps}
""")