import os
import time
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from app.core.dependencies import get_agent_graph, get_agent_service
from app.services.agent.agent_service import AgentService

from app.schemas.agent.agent_request import AgentRequest
from app.schemas.agent.agent_response import AgentResponse
from app.services.llm.llm_service import LLMService


router = APIRouter()

@router.post("/agent_langgraph/chat", response_model=AgentResponse)
async def chat_with_langgraph_agent(
    query: str = Form(..., description="Query"),
    file: Optional[UploadFile] = File(None, description="Optional file for context"),
    graph: CompiledStateGraph = Depends(get_agent_graph),
    agent_service: AgentService = Depends(get_agent_service)
):
    try:
        # Delegate all business logic to the service
        return await agent_service.process_langgraph_chat(query, file, graph)
        
    except Exception as e:
        logger.error(f"Graph Execution Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")