"""Pydantic schemas for usage analytics."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# --- Provider / Model aggregation items ---

class UsageProviderItem(BaseModel):
    """Aggregated stats for a single provider."""

    name: str
    requests: int = 0
    promptTokens: int = 0
    completionTokens: int = 0
    cost: float = 0.0


class UsageModelItem(BaseModel):
    """Aggregated stats for a single model."""

    name: str
    provider: str
    requests: int = 0
    promptTokens: int = 0
    completionTokens: int = 0
    cost: float = 0.0
    lastUsed: Optional[str] = None


class UsageAccountItem(BaseModel):
    """Aggregated stats for a single account (connection)."""

    connectionId: str
    accountName: str
    rawModel: str
    provider: str
    requests: int = 0
    promptTokens: int = 0
    completionTokens: int = 0
    cost: float = 0.0
    lastUsed: Optional[str] = None


class UsageApiKeyItem(BaseModel):
    """Aggregated stats for a single API key."""

    keyName: str
    rawModel: str
    provider: str
    requests: int = 0
    promptTokens: int = 0
    completionTokens: int = 0
    cost: float = 0.0
    lastUsed: Optional[str] = None


class UsageEndpointItem(BaseModel):
    """Aggregated stats for a single endpoint."""

    endpoint: str
    rawModel: str
    provider: str
    requests: int = 0
    promptTokens: int = 0
    completionTokens: int = 0
    cost: float = 0.0
    lastUsed: Optional[str] = None


class RecentRequestItem(BaseModel):
    """A single recent request for the live feed."""

    timestamp: str
    model: str
    provider: str
    promptTokens: int = 0
    completionTokens: int = 0
    status: str = "ok"


class TopApiKeyItem(BaseModel):
    """Aggregated stats for a single API key in the top-keys table."""

    keyName: str
    cost: float = 0.0
    requests: int = 0
    inputTokens: int = 0
    outputTokens: int = 0
    cacheCreationTokens: int = 0
    cacheReadTokens: int = 0
    totalTokens: int = 0
    totalCost: float = 0.0


# --- Response schemas ---

class UsageStatsOut(BaseModel):
    """Aggregated usage statistics for a period."""

    totalRequests: int = 0
    totalPromptTokens: int = 0
    totalCompletionTokens: int = 0
    totalCacheCreationTokens: int = 0
    totalCacheReadTokens: int = 0
    totalCost: float = 0.0
    costChange: float = 0.0
    costPerRequest: float = 0.0
    byProvider: list[UsageProviderItem] = []
    byModel: list[UsageModelItem] = []
    byAccount: list[UsageAccountItem] = []
    byApiKey: list[UsageApiKeyItem] = []
    byEndpoint: list[UsageEndpointItem] = []
    topApiKeys: list[TopApiKeyItem] = []
    recentRequests: list[RecentRequestItem] = []


class UsageChartPoint(BaseModel):
    """Single data point for the usage chart."""

    label: str
    tokens: int = 0
    cost: float = 0.0


class UsageHistoryOut(BaseModel):
    """Single usage history record."""

    id: int
    timestamp: datetime
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    status: str = "ok"
    tokens: Any = {}
    meta: Any = {}

    model_config = {"from_attributes": True}


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class RequestDetailOut(BaseModel):
    """Full request detail with payloads."""

    id: int
    timestamp: datetime
    provider: Optional[str] = None
    model: Optional[str] = None
    connection_id: Optional[str] = None
    status: str = "ok"
    latency_ttft: Optional[int] = None
    latency_total: Optional[int] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    request: Any = None
    provider_request: Any = None
    provider_response: Any = None
    response: Any = None

    model_config = {"from_attributes": True}


class UsageRequestDetailsOut(BaseModel):
    """Paginated request details response."""

    details: list[RequestDetailOut] = []
    pagination: PaginationInfo
