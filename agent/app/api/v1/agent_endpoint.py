import json
import uuid
from typing import Any, List, Optional
from warnings import deprecated
from fastapi import APIRouter, Depends, Form, HTTPException, Body
from fastapi.responses import StreamingResponse

from loguru import logger
from app.schemas.agent.agent_request import ChatStreamRequest
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
    request: ChatStreamRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Streams the agent reasoning process via SSE using a JSON payload."""
    logger.debug(f"DEBUG API: incoming query is -> '{request.query}'")
    # 1. Format the resume payload if feedback exists
    resume_payload = None
    if request.human_feedback:
        # Pydantic's .model_dump() converts it cleanly to the dict LangGraph expects
        # exclude_none=True ensures we don't pass empty 'feedback' keys if they used the UI editor
        resume_payload = request.human_feedback.model_dump(exclude_none=True)
    
    # 2. Trigger the stream
    return StreamingResponse(
        agent_service.process_langgraph_chat_stream(
            thread_id=request.thread_id,
            query=request.query or "",
            resume_payload=resume_payload,
            project_id=request.project_id,
            dataset_ids=request.dataset_ids
        ),
        media_type="text/event-stream"
    )
