from datetime import datetime
from typing import Any, ClassVar, Dict, Optional
import uuid
from sqlmodel import Column, Field, SQLModel
from sqlalchemy.dialects.postgresql import JSONB

from app.common.constants import MessageRole, MessageType

class ChatMessage(SQLModel, table=True):
    __tablename__: ClassVar[Any]  = "chat_messages"
    __table_args__ = {"schema": "langgraph"}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    thread_id: uuid.UUID = Field(index=True)
    execution_id: Optional[uuid.UUID] = Field(index=True)
    role: MessageRole
    type: MessageType = Field(default=MessageType.ANSWER)
    content: str
    chat_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    created_at: datetime = Field(default_factory=datetime.now)
