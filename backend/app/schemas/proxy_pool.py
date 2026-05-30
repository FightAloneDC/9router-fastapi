"""Pydantic schemas for proxy pools."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProxyPoolCreate(BaseModel):
    """Payload for creating a new proxy pool."""

    name: str
    proxy_url: str
    no_proxy: Optional[str] = None
    pool_type: str = "http"
    is_active: bool = True
    strict_proxy: bool = False


class ProxyPoolUpdate(BaseModel):
    """Partial update for a proxy pool."""

    name: Optional[str] = None
    proxy_url: Optional[str] = None
    no_proxy: Optional[str] = None
    pool_type: Optional[str] = None
    is_active: Optional[bool] = None
    strict_proxy: Optional[bool] = None


class ProxyPoolOut(BaseModel):
    """Public proxy pool representation."""

    id: uuid.UUID
    name: str
    proxy_url: str
    no_proxy: Optional[str] = None
    pool_type: str
    is_active: bool
    strict_proxy: bool
    test_status: Optional[str] = None
    last_tested_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProxyPoolTestResult(BaseModel):
    """Result of a proxy connectivity test."""

    id: uuid.UUID
    status: str  # "active" or "error"
    latency_ms: Optional[float] = None
    error: Optional[str] = None
