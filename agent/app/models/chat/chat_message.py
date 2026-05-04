from datetime import datetime
from typing import Any, ClassVar, Dict, Optional
import uuid
from sqlmodel import Column, Field, SQLModel
from sqlalchemy.dialects.postgresql import JSONB

class ChatMessage(SQLModel, table=True):
    __tablename__: ClassVar[Any]  = "chat_messages"
    __table_args__ = {"schema": "langgraph"}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    thread_id: uuid.UUID = Field(index=True)
    execution_id: Optional[uuid.UUID] = Field(index=True)
    role: str # 'user' or 'assistant'
    type: str = Field(default="answer") # 'answer', 'thought', 'error'
    content: str
    chat_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    created_at: datetime = Field(default_factory=datetime.now)
