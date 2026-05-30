"""Pydantic schemas for chat conversations and messages."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class MessageCreate(BaseModel):
    """Payload for saving a message."""

    role: str
    content: str


class MessageOut(BaseModel):
    """Public message representation."""

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    """Payload for creating a new conversation."""

    title: str = "New Chat"
    model: str | None = None


class ConversationUpdate(BaseModel):
    """Partial update for a conversation."""

    title: str | None = None


class ConversationSummaryOut(BaseModel):
    """Conversation summary for list view (no messages)."""

    id: uuid.UUID
    title: str
    model: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    """Full conversation with messages."""

    id: uuid.UUID
    title: str
    model: str | None = None
    messages: list[MessageOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
