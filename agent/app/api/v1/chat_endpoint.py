from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from loguru import logger
from openai import files

from app.core.dependencies import get_agent_service
from app.services.agent.agent_service import AgentService

from app.schemas.agent.agent_response import AgentResponse


router = APIRouter()

@router.post("/agent_langgraph/chat", response_model=AgentResponse)
async def chat_with_langgraph_agent(
    thread_id: Optional[uuid.UUID] = Form(None, description="Conversation Thread ID"),
    query: str = Form(..., description="Query"),
    files: Optional[List[UploadFile]] = File(default_factory=list, description="Optional file for context"),
    agent_service: AgentService = Depends(get_agent_service),
):
    active_thread_id = thread_id or uuid.uuid4()

    try:
        # Delegate all business logic to the service
        return await agent_service.process_langgraph_chat(active_thread_id, query, files)
        
    except Exception as e:
        logger.error("Graph Execution Error: {e}", e=e)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
    
@router.get("/agent_langgraph/chat/{thread_id}/history")
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