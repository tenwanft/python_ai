from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ChatMessageCreate(BaseModel):
    role: str  # user/assistant/system
    content: str
    model: Optional[str] = None

class ChatMessageRead(BaseModel):
    id: int
    role: str
    content: str
    model: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionCreate(BaseModel):
    user_id: Optional[int] = None
    title: Optional[str] = None

class ChatSessionRead(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageRead] = []

    class Config:
        from_attributes = True