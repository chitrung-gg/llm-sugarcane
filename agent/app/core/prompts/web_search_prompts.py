from langchain_core.prompts import PromptTemplate

WEB_SEARCH_QUERY_OPTIMIZATION_PROMPT = PromptTemplate.from_template(
    """
    You are a Search Query Optimizer. The user is asking a conversational question.
    Convert the user's latest query into a standalone, keyword-dense search engine query.

    CONVERSATION SUMMARY:
    {conversation_summary}

    RULES:
    - DO NOT use conversational filler (remove "I want to know more about", "What is").
    - Resolve pronouns ("it", "this gene") using the summary.
    - Output ONLY the optimized search string.
    """
)