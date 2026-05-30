"""Pydantic schemas for CLI tool configs."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class CliToolConfigOut(BaseModel):
    """Public CLI tool config representation."""

    id: str
    enabled: bool
    config_data: Any = {}
    last_configured_at: Optional[datetime] = None

    @field_validator("config_data", mode="before")
    @classmethod
    def parse_config_data(cls, v: Any) -> Any:
        """Parse JSON string from database into dict."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return v or {}

    model_config = {"from_attributes": True}


class CliToolConfigUpdate(BaseModel):
    """Partial update for CLI tool config."""

    enabled: Optional[bool] = None
    config_data: Optional[Any] = None
