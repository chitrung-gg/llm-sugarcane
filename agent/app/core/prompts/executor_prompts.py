from langchain_core.prompts import PromptTemplate

EXECUTOR_INNER_QUERY_PROMPT = PromptTemplate.from_template("""
Execute this task: {step_description}

--- CONTEXT FROM PREVIOUS STEPS ---
{history_context}
""")