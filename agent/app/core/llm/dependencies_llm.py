from functools import lru_cache
import os
from fastapi import Depends
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import api_key, max_retries
from app.core.tools.genome_tool import list_genome_files
from app.services.agent.agent_service import AgentService
from app.core.tools.post_tool import create_post, get_user_posts
from app.core.llm.gemini_llm import GeminiLLM
from app.services.llm.llm_service import LLMService


def get_llm_service() -> LLMService:
    registry = [
        GeminiLLM()
    ]

    return LLMService(
        model_registry=registry,
        max_retries=3
    )

@lru_cache
def get_agent_model():
    print("Initializing Model and Related Tools ...")

    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.0,
        max_retries=3,
        api_key=os.getenv("GOOGLE_API_KEY")
    )

    tools = [create_post, get_user_posts, list_genome_files]
    model_with_tools = llm.bind_tools(tools=tools)

    return model_with_tools

def get_agent_service(model = Depends(get_agent_model)) -> AgentService:
    return AgentService(model=model)