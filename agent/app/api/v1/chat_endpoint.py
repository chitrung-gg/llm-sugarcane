import time
from fastapi import APIRouter, Depends, HTTPException

from app.services.agent.agent_service import AgentService
from app.core.llm.dependencies_llm import get_agent_model, get_agent_service, get_llm_service
from app.schemas.agent.agent_request import AgentRequest
from app.schemas.agent.agent_response import AgentResponse
from app.services.llm.llm_service import LLMService


router = APIRouter()

@router.post("/agent_sdk/chat", response_model=AgentResponse)
async def chat_with_agent_default_sdk(
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


@router.post("/agent_langchain/chat", response_model=AgentResponse)
async def chat_with_agent_langchain(
    request: AgentRequest,
    service: AgentService = Depends(get_agent_service)
):
    start_time = time.time()
    try:
        # Gọi service thực thi
        service_result = service.process_query(request=request)

        process_time = time.time() - start_time
        
        return AgentResponse(
            answer=service_result["answer"],
            tool_executions=service_result["tool_executions"],
            execution_time=process_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))