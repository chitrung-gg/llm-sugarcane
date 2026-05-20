import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from app.common.constants import MessageRole, MessageType
from app.models.chat.chat_message import ChatMessage
from app.models.chat.chat_thread import ChatThread
from app.configs.storage.databases import langgraph_connection_pool

class ChatService:
    """Handles CRUD operations for Chat Threads and Messages in the LangGraph schema."""

    async def create_thread(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        title: Optional[str] = None
    ) -> ChatThread:
        """Creates a new chat thread."""
        async with langgraph_connection_pool.connection() as conn:
            _id = uuid.uuid4()
            now = datetime.now()
            await conn.execute(
                """
                INSERT INTO langgraph.chat_threads (id, user_id, thread_id, project_id, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (_id, user_id, thread_id, project_id, title, now, now)
            )
            return ChatThread(
                id=_id, user_id=user_id, thread_id=thread_id, 
                project_id=project_id, title=title, created_at=now, updated_at=now
            )

    async def get_thread(self, thread_id: uuid.UUID) -> Optional[ChatThread]:
        """Fetches a specific thread by its LangGraph thread_id."""
        async with langgraph_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM langgraph.chat_threads WHERE thread_id = %s",
                (thread_id,)
            )
            row = await cursor.fetchone()
            if row:
                return ChatThread(**row)
            return None

    async def update_thread_title(self, thread_id: uuid.UUID, title: str) -> bool:
        """Updates the generated title of a thread."""
        async with langgraph_connection_pool.connection() as conn:
            await conn.execute(
                "UPDATE langgraph.chat_threads SET title = %s, updated_at = %s WHERE thread_id = %s",
                (title, datetime.now(), thread_id)
            )
            return True

    async def delete_thread(self, thread_id: uuid.UUID) -> bool:
        """Deletes a thread and cascades to delete all its messages."""
        async with langgraph_connection_pool.connection() as conn:
            # Delete messages first to prevent foreign key constraint violations
            await conn.execute("DELETE FROM langgraph.chat_messages WHERE thread_id = %s", (thread_id,))
            await conn.execute("DELETE FROM langgraph.chat_threads WHERE thread_id = %s", (thread_id,))
            return True

    async def add_message(
        self,
        thread_id: uuid.UUID,
        role: MessageRole,
        content: str,
        execution_id: Optional[uuid.UUID] = None,
        msg_type: MessageType = MessageType.ANSWER,
        chat_metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """Saves a single chat message (User Query, AI Output)."""
        async with langgraph_connection_pool.connection() as conn:
            _id = uuid.uuid4()
            now = datetime.now()
            await conn.execute(
                """
                INSERT INTO langgraph.chat_messages (id, thread_id, execution_id, role, type, content, chat_metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    _id, thread_id, execution_id, role, msg_type, content, 
                    json.dumps(chat_metadata) if chat_metadata else None, now
                )
            )
            
            # Bump the thread's updated_at timestamp
            await conn.execute(
                "UPDATE langgraph.chat_threads SET updated_at = %s WHERE thread_id = %s",
                (now, thread_id)
            )
            
            return ChatMessage(
                id=_id, thread_id=thread_id, execution_id=execution_id, 
                role=role, type=msg_type, content=content, 
                chat_metadata=chat_metadata, created_at=now
            )

    async def get_messages_by_thread(self, thread_id: uuid.UUID) -> List[ChatMessage]:
        """Fetches the full message history for a thread."""
        async with langgraph_connection_pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM langgraph.chat_messages WHERE thread_id = %s ORDER BY created_at ASC",
                (thread_id,)
            )
            rows = await cursor.fetchall()
            return [ChatMessage(**row) for row in rows]

    async def get_recent_chat_turns(self, thread_id: uuid.UUID, limit: int = 3) -> List[str]:
        """
        Fetches the last N conversational turns directly from the database.
        """
        async with langgraph_connection_pool.connection() as conn:
            # A turn is 1 user query + 1 AI answer, so we fetch limit * 2.
            cursor = await conn.execute(
                """
                SELECT role, content
                FROM langgraph.chat_messages
                WHERE thread_id = %s
                  AND (type = 'query' OR type = 'answer')
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (thread_id, limit * 2)
            )
            rows = await cursor.fetchall()
            
            if not rows:
                return []
                
            messages = []
            for row in reversed(rows):
                messages.append(f"{row['role']}: {row['content']}")
                
            return messages