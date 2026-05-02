import asyncio
from enum import StrEnum
import time
from typing import Literal
from langfuse import observe
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, RemoveMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from app.common.constants import ObservationType
from app.configs.settings.settings import get_settings
from app.utils.observability.tracing import tracing
from app.core.graph.nodes.agent_graph_node import AgentGraphNode
from app.core.graph.state.agent_state import AgentState
from app.services.llm.llm_service import LLMService
from app.core.prompts.summarizer_prompts import SUMMARIZER_SYSTEM_PROMPT
from app.utils.pipelines.airflow_client import trigger_airflow_dag

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
    @tracing(observation_type=ObservationType.CHAIN)
    async def summarize_conversation(state: AgentState) -> Command[
        Literal[AgentGraphNode.END_NODE]
    ]:
        settings = get_settings()
        
        summary = state.get("summary", "")
        messages = state.get("messages", [])

        max_messages = settings.SUMMARIZER_SUMMARY_TRIGGER_THRESHOLD
        keep_messages = settings.SUMMARIZER_SUMMARY_KEEP_LAST_N
        timeout_sec = settings.SUMMARIZER_SUMMARY_TIMEOUT_SEC

        # 1. Final Ingestion Dispatch
        pending_knowledge = state.get("extracted_knowledge", [])
        if pending_knowledge:
            logger.info(f"[Summarizer] Dispatching {len(pending_knowledge)} accumulated items to Airflow.")
            try:
                # We use asyncio.to_thread to prevent blocking the event loop
                await asyncio.to_thread(
                    trigger_airflow_dag,
                    conf_payload={"batch": pending_knowledge},
                    dag_id="knowledge_ingestion_pipeline"
                )
            except Exception as e:
                logger.error(f"[Summarizer] Failed to dispatch deferred ingestion: {e}")

        # Only summarize if we have a significant number of messages (e.g., > 10)
        # to avoid summarizing every single turn which is expensive.
        if len(messages) <= max_messages:
            logger.debug("[Summarizer] Not enough messages to summarize. Skipping.")
            return Command(
                goto=AgentGraphNode.END_NODE
            )

        logger.info(f"[Summarizer] 📝 Summarizing {len(messages)} messages...")
        start_time = time.time()
        
        if summary:
            summary_message = f"This is the existing conversation summary:\n{summary}\n\nExtend this summary by incorporating the new messages."
        else:
            summary_message = "Create a summary of the conversation below."

        system_prompt = SUMMARIZER_SYSTEM_PROMPT.format(
            summary_message=summary_message
        )

        # Keep the last N messages out of the summary for immediate context
        messages_to_summarize = messages[:-keep_messages]
        
        try:
            # Prepare the prompt for the summarizer
            llm = llm_service.get_structured_tertiary_model(SummaryOutput)
            
            response = await asyncio.wait_for(
                llm.ainvoke([SystemMessage(content=system_prompt)] + messages_to_summarize),
                timeout=timeout_sec
            )

            new_summary = response.new_summary

            # Create RemoveMessage instructions to delete the messages we just summarized
            # LangGraph uses these to prune the 'messages' list in the state.
            delete_messages = [RemoveMessage(id=m.id) for m in messages_to_summarize if hasattr(m, 'id') and m.id]

            elapsed = int((time.time() - start_time) * 1000)
            logger.debug(f"[Summarizer] ✅ Summary updated in {elapsed}ms. Marked {len(delete_messages)} messages for removal.")

            return Command(
                goto=AgentGraphNode.END_NODE,
                update={
                    "summary": new_summary,
                    "messages": delete_messages
                }
            )
        except Exception as e:
            logger.error(f"[Summarizer] ❌ Summarization failed ({e}). Skipping message deletion to preserve context.")
            return Command(goto=AgentGraphNode.END_NODE)

    return summarize_conversation
