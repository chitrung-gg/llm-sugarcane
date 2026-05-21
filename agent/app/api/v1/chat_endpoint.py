import uuid
from fastapi import APIRouter, Depends

from app.core.dependencies import get_chat_service
from app.services.workspace.chat.chat_service import ChatService

router = APIRouter()


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: uuid.UUID,
    chat_service: ChatService = Depends(get_chat_service)
):
    success = await chat_service.delete_thread(thread_id)
    return {"success": success}
