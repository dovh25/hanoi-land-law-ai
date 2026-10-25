from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str = Field(min_length=1, max_length=10000)
    session_id: Optional[str] = None  # If None, creates new session


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    reply: str
    sources: Optional[List[Dict[str, Any]]] = None
    session_id: str  # Always return session_id (created or existing)
