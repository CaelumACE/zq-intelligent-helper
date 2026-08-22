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


class Reference(BaseModel):
    title: str
    source: str
    snippet: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    content: str
    references: List[Reference] = Field(default_factory=list)
    retrieval_time_ms: Optional[float] = None
    generation_time_ms: Optional[float] = None


__all__ = [
    'MessageRole',
    'ChatMessage',
    'Reference',
    'ChatRequest',
    'ChatResponse',
]
