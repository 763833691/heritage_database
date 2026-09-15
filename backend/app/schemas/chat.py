from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    sources: List[str] = []
    chart_data: Optional[Dict[str, Any]] = None


class ConversationMeta(BaseModel):
    """会话元数据"""
    id: str
    title: str
    message_count: int
    created_at: str
    last_active: str


class ConversationListResponse(BaseModel):
    conversations: List[ConversationMeta]
