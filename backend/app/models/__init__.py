"""数据模型"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class MessageRole(str, Enum):
    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'


class ChatMessage(BaseModel):
    role: MessageRole
    content: str

    def to_dict(self):
        return {"role": self.role.value, "content": self.content}


class Reference(BaseModel):
    title: str
    source: str
    snippet: str

    def to_dict(self):
        return {"title": self.title, "source": self.source, "snippet": self.snippet}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: List[ChatMessage] = Field(default_factory=list)
    provider: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: Optional[str] = None
    content: str
    references: List[Reference] = Field(default_factory=list)
    retrieval_time_ms: Optional[float] = None
    generation_time_ms: Optional[float] = None


class SessionCreate(BaseModel):
    title: str = "新对话"


class SessionResponse(BaseModel):
    id: str
    title: str
    messages: List[dict] = Field(default_factory=list)
    createdAt: int = 0
    updatedAt: int = 0


__all__ = [
    'MessageRole',
    'ChatMessage',
    'Reference',
    'ChatRequest',
    'ChatResponse',
    'SessionCreate',
    'SessionResponse',
]
