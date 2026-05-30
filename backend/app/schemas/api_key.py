"""Pydantic schemas for API keys."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Request schemas ---

class ApiKeyCreate(BaseModel):
    """Payload for creating a new API key."""

    name: Optional[str] = None


# --- Response schemas ---

class ApiKeyOut(BaseModel):
    """Public API key representation."""

    id: uuid.UUID
    key: str
    name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyList(BaseModel):
    """List of API keys."""

    keys: list[ApiKeyOut]
