"""Pydantic schemas for combos."""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

# Name must contain only letters, numbers, underscores, dots, and hyphens
_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")


class ComboCreate(BaseModel):
    """Payload for creating a new combo."""

    name: str
    models: list[str] = []
    kind: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(
                "Name must contain only letters, numbers, hyphens, underscores, and dots"
            )
        return v


class ComboUpdate(BaseModel):
    """Partial update for a combo."""

    name: Optional[str] = None
    models: Optional[list[str]] = None
    kind: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None and not _NAME_RE.match(v):
            raise ValueError(
                "Name must contain only letters, numbers, hyphens, underscores, and dots"
            )
        return v


class ComboOut(BaseModel):
    """Public combo representation."""

    id: uuid.UUID
    name: str
    kind: Optional[str] = None
    models: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
