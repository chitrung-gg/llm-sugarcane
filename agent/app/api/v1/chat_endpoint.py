import json
import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Body
from fastapi.responses import StreamingResponse

from loguru import logger
from app.core.dependencies import get_agent_service
from app.services.agent.agent_service import AgentService
from app.schemas.agent.agent_response import AgentResponse

router = APIRouter()

@router.post("", response_model=AgentResponse)
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
    thread_id: Optional[uuid.UUID] = Form(None, description="Conversation Thread ID"),
    query: str = Form(..., description="Query"),
    project_id: Optional[uuid.UUID] = Form(None, description="Project ID"),
    dataset_ids: Optional[List[uuid.UUID]] = Form(None, description="JSON string of dataset UUIDs"),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Streams the agent reasoning process via SSE."""
    active_thread_id = thread_id or uuid.uuid4()
    parsed_dataset_ids = dataset_ids or []
    
    return StreamingResponse(
        agent_service.process_langgraph_chat_stream(
            thread_id=active_thread_id,
            query=query,
            project_id=project_id,
            dataset_ids=parsed_dataset_ids
        ),
        media_type="text/event-stream"
    )

@router.post("/{thread_id}/resume")
async def resume_chat(
    thread_id: uuid.UUID,
    feedback: Any = Body(...),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Resumes a thread that was interrupted for human feedback."""
    try:
        return await agent_service.resume_graph(thread_id, feedback)
    except Exception as e:
        logger.error(f"Failed to resume thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume thread: {str(e)}")
    
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
