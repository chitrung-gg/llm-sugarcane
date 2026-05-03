import json
import uuid
from typing import Any, List, Optional
from warnings import deprecated
from fastapi import APIRouter, Depends, Form, HTTPException, Body
from fastapi.responses import StreamingResponse

from loguru import logger
from app.common.constants import UserFeedbackAction
from app.core.dependencies import get_agent_service
from app.services.agent.agent_service import AgentService
from app.schemas.agent.agent_response import AgentResponse

router = APIRouter()

@router.post("", response_model=AgentResponse)
@deprecated("Use 'chat_stream()' instead")
async def chat_with_langgraph_agent(
    thread_id: Optional[uuid.UUID] = Form(None, description="Conversation Thread ID"),
    query: str = Form(..., description="Query"),
    project_id: Optional[uuid.UUID] = Form(None, description="Project ID"),
    dataset_ids: Optional[List[uuid.UUID]] = Form(None, description="JSON string of dataset UUIDs"),
    agent_service: AgentService = Depends(get_agent_service),
):
    active_thread_id = thread_id or uuid.uuid4()
    parsed_dataset_ids = dataset_ids or []
    
    try:
        return await agent_service.process_langgraph_chat(
            thread_id=active_thread_id, 
            query=query, 
            project_id=project_id,
            dataset_ids=parsed_dataset_ids
        )
        
    except Exception as e:
        logger.error("Graph Execution Error: {e}", e=e)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

@router.post("/stream")
async def chat_stream(
    thread_id: uuid.UUID = Body(..., description="Conversation Thread ID"),
    query: Optional[str] = Body(None, description="New query (if starting fresh)"),
    human_feedback: Optional[str] = Body(None, description="String from UI: 'APPROVE' or typed text"),
    project_id: Optional[uuid.UUID] = Body(None, description="Project ID"),
    dataset_ids: Optional[List[uuid.UUID]] = Body(None, description="List of dataset UUIDs"),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Streams the agent reasoning process via SSE using a JSON payload."""
    
    parsed_dataset_ids = dataset_ids or []

    resume_payload = None
    if human_feedback:
        if human_feedback == "APPROVE":
            resume_payload = {"action": UserFeedbackAction.APPROVE}
        else:
            resume_payload = {"action": UserFeedbackAction.MODIFY, "feedback": human_feedback}
    
    return StreamingResponse(
        agent_service.process_langgraph_chat_stream(
            thread_id=thread_id,
            query=query or "",
            resume_payload=resume_payload,
            project_id=project_id,
            dataset_ids=parsed_dataset_ids
        ),
        media_type="text/event-stream"
    )
    
@router.get("/{thread_id}/history")
async def get_chat_history(
    thread_id: uuid.UUID,
    agent_service: AgentService = Depends(get_agent_service)
):
    """Fetch the conversation history for a specific thread_id."""
    try:
        return await agent_service.get_conversation_history(thread_id)
    except Exception as e:
        logger.error("Failed to fetch history for thread {thread_id}: {e}", e=e)
        raise HTTPException(status_code=500, detail="Failed to fetch conversation history.")
