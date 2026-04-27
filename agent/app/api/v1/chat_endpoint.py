import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Form, HTTPException

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
