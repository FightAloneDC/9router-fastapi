"""Pydantic schemas for provider connections and provider nodes."""

import uuid
from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel


# --- Provider Connection schemas ---

class ModelEntry(BaseModel):
    """A model entry with id, type, and optional display name."""
    id: str
    type: str = "llm"
    name: Optional[str] = None

class ProviderConnectionCreate(BaseModel):
    """Payload for creating a new provider connection."""

    provider: str
    name: Optional[str] = None
    displayName: Optional[str] = None
    apiKey: str = ""
    auth_type: str = "apikey"
    priority: int = 1
    globalPriority: Optional[int] = None
    defaultModel: Optional[str] = None
    models: list[Union[str, ModelEntry]] = []
    round_robin: bool = False
    baseUrl: Optional[str] = None
    proxyPoolId: Optional[uuid.UUID] = None
    testStatus: Optional[str] = None
    providerSpecificData: Optional[dict] = None
    # Proxy config fields (also accepted inline)
    connectionProxyEnabled: Optional[bool] = None
    connectionProxyUrl: Optional[str] = None
    connectionNoProxy: Optional[str] = None
    noAuth: Optional[bool] = False


class ProviderConnectionUpdate(BaseModel):
    """Partial update for a provider connection."""

    name: Optional[str] = None
    displayName: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    globalPriority: Optional[int] = None
    defaultModel: Optional[str] = None
    models: Optional[list[Union[str, ModelEntry]]] = None
    round_robin: Optional[bool] = None
    apiKey: Optional[str] = None
    baseUrl: Optional[str] = None
    proxyPoolId: Optional[uuid.UUID] = None
    testStatus: Optional[str] = None
    lastError: Optional[str] = None
    lastErrorAt: Optional[str] = None
    providerSpecificData: Optional[dict] = None
    # Proxy config fields
    connectionProxyEnabled: Optional[bool] = None
    connectionProxyUrl: Optional[str] = None
    connectionNoProxy: Optional[str] = None


class ProviderConnectionOut(BaseModel):
    """Public provider connection representation (no sensitive data).

    Matches the flat structure from the original Next.js implementation.
    All provider-specific data is spread into providerSpecificData.
    """

    id: uuid.UUID
    provider: str
    auth_type: str
    name: Optional[str] = None
    email: Optional[str] = None
    displayName: Optional[str] = None
    priority: int
    globalPriority: Optional[int] = None
    is_active: bool
    defaultModel: Optional[str] = None
    test_status: Optional[str] = None
    lastError: Optional[str] = None
    lastErrorAt: Optional[str] = None
    errorCode: Optional[str] = None
    expiresAt: Optional[str] = None
    lastUsedAt: Optional[str] = None
    consecutiveUseCount: Optional[int] = None
    models: list[Union[str, ModelEntry]] = []
    round_robin: bool = False
    base_url: Optional[str] = None
    proxy_pool_id: Optional[uuid.UUID] = None
    providerSpecificData: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    serviceKinds: list[str] = ["llm"]

    model_config = {"from_attributes": True}


# --- Provider validation schemas ---

class ProviderValidateRequest(BaseModel):
    """Payload for validating provider credentials."""

    provider: str
    apiKey: str = ""
    baseUrl: Optional[str] = None
    providerSpecificData: Optional[dict] = None


class ProviderValidateResponse(BaseModel):
    """Result of provider credential validation."""

    valid: bool
    error: Optional[str] = None
    models: Optional[list[str]] = None


# --- Provider test schemas ---

class ProviderTestResponse(BaseModel):
    """Result of testing a single provider connection."""

    valid: bool
    error: Optional[str] = None
    refreshed: bool = False
    latencyMs: Optional[int] = None
    models: Optional[list[str]] = None


class BatchTestResult(BaseModel):
    """Result for a single connection in a batch test."""

    provider: str
    connectionId: str
    connectionName: Optional[str] = None
    authType: Optional[str] = None
    valid: bool
    latencyMs: int = 0
    error: Optional[str] = None
    testedAt: Optional[str] = None


class BatchTestResponse(BaseModel):
    """Result of a batch test operation."""

    mode: str
    providerId: Optional[str] = None
    results: list[BatchTestResult] = []
    summary: dict = {}
    testedAt: Optional[str] = None


class BatchTestRequest(BaseModel):
    """Payload for batch testing connections."""

    mode: str  # provider, apikey, all
    providerId: Optional[str] = None


# --- Suggested Models schemas ---

class SuggestedModelsRequest(BaseModel):
    """Payload for fetching suggested models."""

    url: str
    type: str  # e.g. "openrouter-free", "opencode-free"


class SuggestedModelsResponse(BaseModel):
    """Result of suggested models fetch."""

    data: list = []


# --- Provider Node schemas ---

class ProviderNodeCreate(BaseModel):
    """Payload for creating a custom provider node.

    ``id`` is optional — the server auto-generates one (matching the original
    Next.js behaviour) when it is omitted.
    """

    id: Optional[str] = None
    type: str
    name: str
    base_url: Optional[str] = None
    prefix: str
    api_type: Optional[str] = None


class ProviderNodeUpdate(BaseModel):
    """Partial update for a custom provider node."""

    name: Optional[str] = None
    prefix: Optional[str] = None
    base_url: Optional[str] = None
    api_type: Optional[str] = None


class ProviderNodeOut(BaseModel):
    """Public provider node representation."""

    id: str
    type: str
    name: Optional[str] = None
    base_url: Optional[str] = None
    prefix: Optional[str] = None
    api_type: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProviderNodeValidateRequest(BaseModel):
    """Payload for validating a compatible provider node's API key."""

    baseUrl: str
    apiKey: str
    type: str = "openai-compatible"  # openai-compatible | anthropic-compatible | custom-embedding
    modelId: Optional[str] = None


class ProviderNodeValidateResponse(BaseModel):
    """Result of provider node validation."""

    valid: bool
    error: Optional[str] = None
    method: Optional[str] = None
    dimensions: Optional[int] = None
