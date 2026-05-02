from pydantic import BaseModel
from typing import Any
from app.common.constants import StreamEventType

class StreamChunk(BaseModel):
    event: StreamEventType
    data: Any
