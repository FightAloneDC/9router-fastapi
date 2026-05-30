"""Pydantic schemas for MITM config and logs."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class MitmConfigOut(BaseModel):
    """MITM configuration response."""

    enabled: bool
    port: int
    router_base_url: str
    cert_generated: bool
    tools_config: dict[str, Any]

    @field_validator("tools_config", mode="before")
    @classmethod
    def parse_tools_config(cls, v: Any) -> dict[str, Any]:
        """Parse JSON string into dict."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v or {}

    model_config = {"from_attributes": True}


class MitmConfigUpdate(BaseModel):
    """Partial MITM configuration update."""

    enabled: Optional[bool] = None
    port: Optional[int] = None
    router_base_url: Optional[str] = None
    tools_config: Optional[dict[str, Any]] = None


class MitmLogOut(BaseModel):
    """MITM log entry response."""

    id: int
    timestamp: datetime
    tool: str
    direction: str
    method: Optional[str] = None
    url: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    body_preview: Optional[str] = None

    model_config = {"from_attributes": True}
