from datetime import datetime
from typing import Optional
import uuid
from sqlmodel import Field, SQLModel

class ChatThread(SQLModel, table=True):
    __tablename__ = "chat_threads"
    __table_args__ = {"schema": "langgraph"}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True)
    thread_id: uuid.UUID = Field(index=True, unique=True)
    project_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user_projects.id")
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
