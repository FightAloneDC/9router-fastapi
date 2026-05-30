"""Helper functions for provider data conversion, proxy config, and utilities."""

import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.provider import ProviderConnection, ProviderNode
from app.models.proxy_pool import ProxyPool
from app.routers.providers.constants import _DATA_INTERNAL_KEYS, PROVIDER_DEFAULTS, MODEL_TYPE_OVERRIDES, infer_model_type, normalize_models_list


def _get_base_url(provider: str, body_base_url: Optional[str] = None, extra_data: Optional[dict] = None) -> str:
    """Resolve the effective base URL for a provider."""
    if body_base_url:
        return body_base_url.rstrip("/")

    # Handle region-specific providers (region takes precedence over stored baseUrl)
    if provider == "xiaomi-tokenplan" and extra_data:
        region = extra_data.get("region", "sgp")
        region_urls = {
            "sgp": "https://token-plan-sgp.xiaomimimo.com/v1",
            "cn": "https://token-plan-cn.xiaomimimo.com/v1",
            "ams": "https://token-plan-ams.xiaomimimo.com/v1",
        }
        return region_urls.get(region, region_urls["sgp"]).rstrip("/")

    if extra_data and extra_data.get("baseUrl"):
        return extra_data["baseUrl"].rstrip("/")

    defaults = PROVIDER_DEFAULTS.get(provider, {})
    return defaults.get("baseUrl", "").rstrip("/")


def _get_validation_type(provider: str) -> str:
    """Get the validation strategy for a provider."""
    return PROVIDER_DEFAULTS.get(provider, {}).get("validationType", "openai")


def _connection_to_out(conn: ProviderConnection) -> dict:
    """Convert a ProviderConnection model to output dict.

    Extracts all fields from the data JSON blob and returns them as top-level
    properties, matching the original Next.js flat structure. Sensitive fields
    (apiKey, accessToken, etc.) are excluded.
    """
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    # Extract provider-specific data (everything not in _DATA_INTERNAL_KEYS)
    provider_specific = {k: v for k, v in data.items() if k not in _DATA_INTERNAL_KEYS}

    return {
        "id": conn.id,
        "provider": conn.provider,
        "auth_type": conn.auth_type,
        "name": conn.name,
        "email": conn.email,
        "displayName": data.get("displayName"),
        "priority": conn.priority,
        "globalPriority": data.get("globalPriority"),
        "is_active": conn.is_active,
        "defaultModel": data.get("defaultModel"),
        "test_status": data.get("testStatus"),
        "lastError": data.get("lastError"),
        "lastErrorAt": data.get("lastErrorAt"),
        "errorCode": data.get("errorCode"),
        "expiresAt": data.get("expiresAt"),
        "lastUsedAt": data.get("lastUsedAt"),
        "consecutiveUseCount": data.get("consecutiveUseCount"),
        "models": normalize_models_list(data.get("models", [])),
        "round_robin": data.get("roundRobin", False),
        "base_url": data.get("baseUrl"),
        "proxy_pool_id": conn.proxy_pool_id,
        "providerSpecificData": provider_specific or None,
        "created_at": conn.created_at,
        "updated_at": conn.updated_at,
        "serviceKinds": PROVIDER_DEFAULTS.get(conn.provider, {}).get("serviceKinds", ["llm"]),
    }


def _sanitize_connection(conn_dict: dict) -> dict:
    """Sanitize connection for client-facing output (whitelist only)."""
    SAFE_FIELDS = [
        "id", "provider", "auth_type", "name", "email", "displayName",
        "priority", "globalPriority", "is_active", "defaultModel",
        "test_status", "lastError", "lastErrorAt", "errorCode",
        "expiresAt", "lastUsedAt", "consecutiveUseCount",
        "created_at", "updated_at", "serviceKinds",
    ]
    SAFE_PSD_FIELDS = [
        "baseUrl", "azureEndpoint", "deployment", "apiVersion", "organization", "accountId",
        "accessKeyId", "region", "projectId", "resourceUrl", "proxyPoolId",
        "connectionProxyEnabled", "connectionProxyUrl", "connectionNoProxy",
        "githubLogin", "githubName", "githubEmail", "githubUserId",
        "username", "firstName", "lastName", "authMethod", "authKind",
    ]

    safe = {}
    for f in SAFE_FIELDS:
        if conn_dict.get(f) is not None:
            safe[f] = conn_dict[f]

    psd = conn_dict.get("providerSpecificData")
    if psd and isinstance(psd, dict):
        safe_psd = {k: v for k, v in psd.items() if k in SAFE_PSD_FIELDS and v is not None}
        if safe_psd:
            safe["providerSpecificData"] = safe_psd

    return safe


def _node_to_out(node: ProviderNode) -> dict:
    """Convert a ProviderNode model to ProviderNodeOut dict."""
    data = {}
    try:
        data = json.loads(node.data) if node.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "id": node.id,
        "type": node.type,
        "name": node.name,
        "base_url": data.get("baseUrl"),
        "prefix": data.get("prefix"),
        "api_type": data.get("apiType"),
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


# --- Proxy config helpers ---

def _normalize_proxy_config(body: dict) -> dict:
    """Normalize proxy config from request body."""
    enabled = body.get("connectionProxyEnabled") is True
    url = (body.get("connectionProxyUrl") or "").strip()
    no_proxy = (body.get("connectionNoProxy") or "").strip()

    if enabled and not url:
        return {"error": "Connection proxy URL is required when connection proxy is enabled"}

    return {
        "connectionProxyEnabled": enabled,
        "connectionProxyUrl": url,
        "connectionNoProxy": no_proxy,
    }


async def _normalize_proxy_pool_id(db: AsyncSession, proxy_pool_id) -> dict:
    """Validate and normalize proxy pool ID."""
    if proxy_pool_id is None or proxy_pool_id == "" or str(proxy_pool_id) == "__none__":
        return {"proxyPoolId": None}

    pool_id = str(proxy_pool_id).strip()
    if not pool_id:
        return {"proxyPoolId": None}

    try:
        uid = pool_id if isinstance(pool_id, type(proxy_pool_id)) else pool_id
        result = await db.execute(
            select(ProxyPool).where(ProxyPool.id == uid)
        )
        pool = result.scalar_one_or_none()
        if not pool:
            return {"error": "Proxy pool not found"}
    except Exception:
        return {"error": "Invalid proxy pool ID"}

    return {"proxyPoolId": pool_id}


# --- Model parsing helpers ---

def _parse_openai_models(data):
    """Parse OpenAI-style model list."""
    if isinstance(data, dict):
        return data.get("data", data.get("models", data.get("results", [])))
    if isinstance(data, list):
        return data
    return []


def _normalize_model(m):
    """Normalize a model entry to {id, name, type}."""
    if isinstance(m, str):
        return {"id": m, "name": m, "type": infer_model_type(m)}
    model_id = m.get("id") or m.get("name") or m.get("model", "")
    name = m.get("name") or m.get("display_name") or m.get("displayName") or m.get("id", "")
    model_type = m.get("type") or MODEL_TYPE_OVERRIDES.get(model_id) or infer_model_type(model_id)
    return {"id": model_id, "name": name, "type": model_type}


def _get_models_error_message(status_code: int) -> str:
    if status_code in (401, 403):
        return "API key unauthorized"
    if status_code == 404:
        return "/models endpoint not found - try chat validation with model ID"
    if status_code >= 500:
        return "Server error - try again later"
    return f"Unexpected response ({status_code})"


def _get_chat_error_message(status_code: int) -> str:
    if status_code in (401, 403):
        return "API key unauthorized"
    if status_code == 400:
        return "Invalid model or bad request"
    if status_code == 404:
        return "Chat endpoint not found"
    if status_code >= 500:
        return "Server error - try again later"
    return f"Chat request failed ({status_code})"
