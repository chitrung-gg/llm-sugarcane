from enum import StrEnum
from typing import Literal
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, RemoveMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService

class SummaryOutput(BaseModel):
    """
    Schema for the LLM to output a structured conversation summary.
    """
    new_summary: str = Field(
        description="The comprehensive summary of the conversation to date, gracefully incorporating the new messages."
    )

def make_summarizer_node(llm_service: LLMService):
    """
    Creates a node that summarizes the conversation history to keep the context window lean.
    This follows the 'Summarize-and-Delete' pattern from LangGraph.
    """
    @tracing
    async def summarize_conversation(state: AgentState) -> Command[
        Literal[AgentGraphNode.END_NODE]
    ]:
        summary = state.get("summary", "")
        messages = state.get("messages", [])

        # Only summarize if we have a significant number of messages (e.g., > 6)
        # to avoid summarizing every single turn which is expensive.
        if len(messages) <= 6:
            logger.debug("[Summarizer] Not enough messages to summarize. Skipping.")
            return Command(
                goto=AgentGraphNode.END_NODE
            )

        logger.debug(f"[Summarizer] 📝 Summarizing {len(messages)} messages...")

        if summary:
            # If a summary already exists, we append the new messages to it
            summary_message = f"This is a summary of the conversation to date: {summary}\n\nExtend the summary by taking into account the following new messages:"
        else:
            summary_message = "Create a summary of the conversation below:"

        # We keep the last 2 messages out of the summary so the LLM has immediate context
        messages_to_summarize = messages[:-2]
        
        # Prepare the prompt for the summarizer
        llm = llm_service.get_structured_tertiary_model(SummaryOutput)
        
        response = await llm.ainvoke(
            [
                SystemMessage(content=summary_message),
                *messages_to_summarize
            ]
        )

        new_summary = response.new_summary

        # Create RemoveMessage instructions to delete the messages we just summarized
        # LangGraph uses these to prune the 'messages' list in the state.
        delete_messages = [RemoveMessage(id=m.id) for m in messages_to_summarize if hasattr(m, 'id') and m.id]

        logger.debug("[Summarizer] ✅ Summary updated and old messages marked for removal.")

        return Command(
            goto=AgentGraphNode.END_NODE,
            update={
                "summary": new_summary,
                "messages": delete_messages
            }
        )

    return summarize_conversation
