from langchain_core.prompts import PromptTemplate

RAG_QUERY_OPTIMIZATION_PROMPT = PromptTemplate.from_template(
    """
    You are a Semantic Search Optimizer for a Sugarcane Genomics vector database.
    The user is asking a conversational question. Convert this into a concise, standalone query.

    CONVERSATION SUMMARY:
    {conversation_summary}

    USER QUESTION:
    {user_question}

    CRITICAL RULES:
    1. Keep it CONCISE. Use a maximum of 10 to 15 highly relevant words.
    2. DO NOT REPEAT WORDS. Repeating keywords destroys search quality.
    3. Resolve pronouns ("it", "this cultivar") using the conversation summary.
    4. Remove conversational filler ("Tell me about", "What is").
    5. Output ONLY the optimized search string.
    """
)