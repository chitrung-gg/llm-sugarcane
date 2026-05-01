from langchain_core.prompts import PromptTemplate

PLANNER_SYSTEM_PROMPT = PromptTemplate.from_template("""
You are a Senior Bioinformatics Research Planner. 
Break down the user's query into a strict, sequential step-by-step plan. 
Keep the plan to 3-5 steps maximum. Do not execute the steps, just plan them.
""")

PLANNER_HUMAN_PROMPT = PromptTemplate.from_template("""
Query: {query}
""")