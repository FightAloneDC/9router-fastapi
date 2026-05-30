"""Pydantic schemas for authentication."""

import uuid
from datetime import datetime

from pydantic import BaseModel


# --- Request schemas ---

class UserCreate(BaseModel):
    """Payload for user registration."""

    username: str
    password: str


class LoginRequest(BaseModel):
    """Payload for password-only login (9Router pattern)."""

    password: str


# --- Response schemas ---

class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Public user representation."""

    id: uuid.UUID
    username: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthStatus(BaseModel):
    """Auth status response."""

    requireLogin: bool
    hasPassword: bool
