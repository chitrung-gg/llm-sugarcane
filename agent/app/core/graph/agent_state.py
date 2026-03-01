from typing import Annotated, List, TypedDict

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    query: str
    messages: Annotated[List[BaseMessage], add_messages]
    extracted_context: str