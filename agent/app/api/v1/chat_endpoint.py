import time
from fastapi import APIRouter, Depends, HTTPException

from app.core.llm.dependencies_llm import get_llm_service
from app.schemas.chat.agent_request import AgentRequest
from app.schemas.chat.agent_response import AgentResponse
from app.services.llm.llm_service import LLMService


router = APIRouter()

@router.post("/agent/chat", response_model=AgentResponse)
async def chat_with_agent(
    request: AgentRequest,
    service: LLMService = Depends(get_llm_service)
):
    start_time = time.time()
    try:
        if request.context_data:
            result = service.call_with_fallback(f"Can you answer {request.query} with the additional context {request.context_data}?")
        else:
            result = service.call_with_fallback(f"{request.query}")

        process_time = time.time() - start_time

        return AgentResponse(
            answer=result,
            execution_time=process_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))