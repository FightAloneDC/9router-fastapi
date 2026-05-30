"""Provider model fetching and clearing endpoints."""

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.models.settings import SettingsModel
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.constants import PROVIDER_DEFAULTS, normalize_models_list
from app.routers.providers.helpers import _normalize_model, _parse_openai_models

# Provider-specific model fetching configs
PROVIDER_MODELS_CONFIG = {
    "claude": {
        "url": "https://api.anthropic.com/v1/models",
        "method": "GET",
        "headers": {"Anthropic-Version": "2023-06-01", "Content-Type": "application/json"},
        "authHeader": "x-api-key",
        "parseResponse": lambda data: data.get("data", []),
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authQuery": "key",
        "parseResponse": lambda data: [
            {**m, "name": m.get("name", "").replace("models/", "")}
            for m in data.get("models", [])
        ],
    },
    "openai": {
        "url": "https://api.openai.com/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "opencode-go": {
        "url": "https://opencode.ai/zen/go/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "kilocode": {
        "url": "https://api.kilo.ai/api/openrouter/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/models",
        "method": "GET",
        "headers": {"Anthropic-Version": "2023-06-01", "Content-Type": "application/json"},
        "authHeader": "x-api-key",
        "parseResponse": lambda data: data.get("data", []),
    },
    "askcodi": {
        "url": "https://api.askcodi.com/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "deepseek": {
        "url": "https://api.deepseek.com/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "xai": {
        "url": "https://api.x.ai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "mistral": {
        "url": "https://api.mistral.ai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "perplexity": {
        "url": "https://api.perplexity.ai/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "together": {
        "url": "https://api.together.xyz/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "fireworks": {
        "url": "https://api.fireworks.ai/inference/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "cohere": {
        "url": "https://api.cohere.com/compatibility/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        # Cohere's OpenAI-compatibility endpoint returns OpenAI shape:
        # {"object": "list", "data": [{"id": "...", "object": "model", "owned_by": "cohere"}]}
        "parseResponse": lambda data: data.get("data", []),
    },
    "nebius": {
        "url": "https://api.studio.nebius.ai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "siliconflow": {
        "url": "https://api.siliconflow.com/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "hyperbolic": {
        "url": "https://api.hyperbolic.xyz/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "ollama": {
        "url": "https://ollama.com/api/tags",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "parseResponse": lambda data: data.get("models", []),
    },
    "nanobanana": {
        "url": "https://api.nanobananaapi.ai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "chutes": {
        "url": "https://llm.chutes.ai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "nvidia": {
        "url": "https://integrate.api.nvidia.com/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "assemblyai": {
        "url": "https://api.assemblyai.com/v2/transcript?limit=1",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "",
        "parseResponse": lambda data: [{"id": m, "name": m, "type": "stt"} for m in ["universal-3-pro", "universal-2", "nano", "best", "slam-1"]],
    },
    "elevenlabs": {
        "url": "https://api.elevenlabs.io/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "xi-api-key",
        "authPrefix": "",
        "parseResponse": lambda data: [
            {"id": m.get("model_id", ""), "name": m.get("name", ""), "type": "tts"}
            for m in data if m.get("model_id") and m.get("can_do_text_to_speech", False)
        ],
    },
    "deepgram": {
        "url": "https://api.deepgram.com/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Token ",
        "parseResponse": lambda data: [
            {"id": m.get("canonical_name") or m.get("name", ""), "name": m.get("canonical_name") or m.get("name", ""), "type": "tts"}
            for m in data.get("tts", []) if m.get("name")
        ] + [
            {"id": m.get("canonical_name") or m.get("name", ""), "name": m.get("canonical_name") or m.get("name", ""), "type": "stt"}
            for m in data.get("stt", []) if m.get("name")
        ],
    },
    "vercel-ai-gateway": {
        "url": "https://ai-gateway.vercel.sh/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "alicode": {
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "alicode-intl": {
        "url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "volcengine-ark": {
        "url": "https://ark.cn-beijing.volces.com/api/coding/v3/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "byteplus": {
        "url": "https://ark.ap-southeast.bytepluses.com/api/coding/v3/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    # ── Additional API Key providers ──────────────────────────────────────
    "glm": {
        "url": "https://api.z.ai/api/anthropic/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json", "Anthropic-Version": "2023-06-01"},
        "authHeader": "x-api-key",
        "parseResponse": lambda data: data.get("data", []),
    },
    "glm-cn": {
        "url": "https://open.bigmodel.cn/api/coding/paas/v4/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "kimi": {
        "url": "https://api.kimi.com/coding/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json", "Anthropic-Version": "2023-06-01"},
        "authHeader": "x-api-key",
        "parseResponse": lambda data: data.get("data", []),
    },
    "minimax": {
        "url": "https://api.minimax.io/anthropic/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json", "Anthropic-Version": "2023-06-01"},
        "authHeader": "x-api-key",
        "parseResponse": lambda data: data.get("data", []),
    },
    "minimax-cn": {
        "url": "https://api.minimaxi.com/anthropic/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json", "Anthropic-Version": "2023-06-01"},
        "authHeader": "x-api-key",
        "parseResponse": lambda data: data.get("data", []),
    },
    "xiaomi-mimo": {
        "url": "https://api.xiaomimimo.com/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "xiaomi-tokenplan": {
        "url": "https://token-plan-sgp.xiaomimimo.com/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "volcengine": {
        "url": "https://ark.cn-beijing.volces.com/api/v3/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "ollama-local": {
        "url": "http://localhost:11434/api/tags",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "parseResponse": lambda data: data.get("models", []),
    },
    "huggingface": {
        "url": "https://api-inference.huggingface.co/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "tavily": {
        "url": "https://api.tavily.com/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "brave-search": {
        "url": "https://api.search.brave.com/res/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "serper": {
        "url": "https://google.serper.dev/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "exa": {
        "url": "https://api.exa.ai/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "fal-ai": {
        "url": "https://fal.run/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "stability-ai": {
        "url": "https://api.stability.ai/v2beta/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "jina-ai": {
        "url": "https://api.jina.ai/v1/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
    "kilo-gateway": {
        "url": "https://api.kilo.ai/api/gateway/models",
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
        "authHeader": "Authorization",
        "authPrefix": "Bearer ",
        "parseResponse": lambda data: data.get("data", []),
    },
}


@router.get("/providers/{conn_id}/models")
async def fetch_provider_models(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Fetch available models from a provider's API using the connection's credentials."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key = data.get("apiKey", "")
    provider = conn.provider

    # Check if this is a compatible provider (node-based)
    node_result = await db.execute(
        select(ProviderNode).where(ProviderNode.id == provider)
    )
    node = node_result.scalar_one_or_none()

    if node:
        node_data = {}
        try:
            node_data = json.loads(node.data) if node.data else {}
        except (json.JSONDecodeError, TypeError):
            pass
        node_base_url = node_data.get("baseUrl", "")

        if node.type == "openai-compatible":
            if not api_key:
                raise HTTPException(status_code=400, detail="No API key configured for this connection")
            if not node_base_url:
                raise HTTPException(status_code=400, detail="No base URL configured for OpenAI compatible provider")
            url = f"{node_base_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=15.0) as client:
                try:
                    resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                    if not resp.is_success:
                        raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch models: {resp.status_code}")
                    models_raw = _parse_openai_models(resp.json())
                    models = [_normalize_model(m) for m in models_raw if _normalize_model(m)["id"]]
                    data["models"] = [{"id": m["id"], "type": m["type"]} for m in models]
                    conn.data = json.dumps(data)
                    await db.flush()
                    return {"provider": provider, "connectionId": str(conn.id), "models": models}
                except httpx.ConnectError:
                    raise HTTPException(status_code=502, detail=f"Cannot connect to {node_base_url}")
                except httpx.TimeoutException:
                    raise HTTPException(status_code=504, detail="Connection timed out")

        elif node.type == "anthropic-compatible":
            if not api_key:
                raise HTTPException(status_code=400, detail="No API key configured for this connection")
            if not node_base_url:
                raise HTTPException(status_code=400, detail="No base URL configured for Anthropic compatible provider")
            normalized = node_base_url.rstrip("/")
            if normalized.endswith("/messages"):
                normalized = normalized[:-9]
            url = f"{normalized}/models"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Authorization": f"Bearer {api_key}",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                try:
                    resp = await client.get(url, headers=headers)
                    if not resp.is_success:
                        raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch models: {resp.status_code}")
                    models_raw = resp.json().get("data", [])
                    models = [_normalize_model(m) for m in models_raw if _normalize_model(m)["id"]]
                    data["models"] = [{"id": m["id"], "type": m["type"]} for m in models]
                    conn.data = json.dumps(data)
                    await db.flush()
                    return {"provider": provider, "connectionId": str(conn.id), "models": models}
                except httpx.ConnectError:
                    raise HTTPException(status_code=502, detail=f"Cannot connect to {node_base_url}")
                except httpx.TimeoutException:
                    raise HTTPException(status_code=504, detail="Connection timed out")

    # ── Qoder: COSY-signed model fetching ──────────────────────────────────
    if provider == "qoder":
        from app.services.qoder.models import resolve_qoder_models

        credentials = {
            "access_token": data.get("accessToken", ""),
            "email": conn.email,
            "display_name": conn.name,
            "provider_specific": {
                "userId": data.get("userId", ""),
                "machineId": data.get("machineId", ""),
            },
        }

        try:
            result = await resolve_qoder_models(credentials, force_refresh=True)
            models = []
            for m in result.get("models", []):
                models.append({
                    "id": f"qoder/{m['id']}",
                    "name": m.get("name", m["id"]),
                    "type": "llm",
                    "contextLength": m.get("context_length", 0),
                })
            data["models"] = [{"id": m["id"], "type": m["type"]} for m in models]
            conn.data = json.dumps(data)
            await db.flush()
            return {"provider": provider, "connectionId": str(conn.id), "models": models}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch Qoder models: {str(e)}")

    # Provider-specific config
    config = PROVIDER_MODELS_CONFIG.get(provider)
    if not config:
        # Fallback: try OpenAI-compatible with default base URL
        default_url = PROVIDER_DEFAULTS.get(provider, {}).get("baseUrl", "")
        if default_url:
            if not api_key:
                raise HTTPException(status_code=400, detail="No API key configured for this connection")
            url = f"{default_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=15.0) as client:
                try:
                    resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                    if not resp.is_success:
                        raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch models: {resp.status_code}")
                    models_raw = _parse_openai_models(resp.json())
                    models = [_normalize_model(m) for m in models_raw if _normalize_model(m)["id"]]
                    data["models"] = [{"id": m["id"], "type": m["type"]} for m in models]
                    conn.data = json.dumps(data)
                    await db.flush()
                    return {"provider": provider, "connectionId": str(conn.id), "models": models}
                except httpx.ConnectError:
                    raise HTTPException(status_code=502, detail=f"Cannot connect to {default_url}")
                except httpx.TimeoutException:
                    raise HTTPException(status_code=504, detail="Connection timed out")
        raise HTTPException(status_code=400, detail=f"Provider {provider} does not support model fetching")

    # Build request from config
    url = config["url"]
    
    # Handle region-specific URLs
    if provider == "xiaomi-tokenplan":
        region = data.get("region", "sgp")
        region_urls = {
            "sgp": "https://token-plan-sgp.xiaomimimo.com/v1/models",
            "cn": "https://token-plan-cn.xiaomimimo.com/v1/models",
            "ams": "https://token-plan-ams.xiaomimimo.com/v1/models",
        }
        url = region_urls.get(region, region_urls["sgp"])
    
    token = data.get("accessToken") or api_key
    if not token:
        raise HTTPException(status_code=401, detail="No valid token found")

    headers = dict(config.get("headers", {}))
    if config.get("authQuery"):
        url += f"?{config['authQuery']}={token}"
    elif config.get("authHeader"):
        prefix = config.get("authPrefix", "")
        headers[config["authHeader"]] = f"{prefix}{token}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.request(config.get("method", "GET"), url, headers=headers)
            if not resp.is_success:
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch models: {resp.status_code}")
            models_raw = config["parseResponse"](resp.json())
            models = [_normalize_model(m) for m in models_raw if _normalize_model(m)["id"]]
            data["models"] = [{"id": m["id"], "type": m["type"]} for m in models]
            conn.data = json.dumps(data)
            await db.flush()
            return {"provider": provider, "connectionId": str(conn.id), "models": models}
        except httpx.ConnectError:
            raise HTTPException(status_code=502, detail=f"Cannot connect to {config['url']}")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Connection timed out")


@router.delete("/providers/{conn_id}/models")
async def clear_provider_models(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Clear all stored models from a provider connection and remove disabled models for this provider alias."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Parse data JSON
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    # Count current models before clearing
    current_models = data.get("models", [])
    cleared_count = len(current_models) if isinstance(current_models, list) else 0

    # Clear models
    data["models"] = []
    conn.data = json.dumps(data)

    # Also clear disabled models for this provider alias from settings
    provider_alias = conn.provider
    settings_result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    settings_row = settings_result.scalar_one_or_none()
    if settings_row:
        try:
            settings_data = json.loads(settings_row.data) if settings_row.data else {}
        except (json.JSONDecodeError, TypeError):
            settings_data = {}
        disabled = settings_data.get("disabledModels", {})
        if provider_alias in disabled:
            del disabled[provider_alias]
            settings_data["disabledModels"] = disabled
            settings_row.data = json.dumps(settings_data)

    await db.flush()
    return {"ok": True, "clearedCount": cleared_count}


@router.patch("/providers/{conn_id}/models/type")
async def change_model_type(
    conn_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Override the type for a specific model in a provider connection."""
    VALID_TYPES = {"llm", "embedding", "tts", "stt", "image", "imageToText", "video", "music", "webSearch", "webFetch"}

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    model_id = body.get("model_id")
    new_type = body.get("type")
    if not model_id or not new_type:
        raise HTTPException(status_code=400, detail="model_id and type are required")
    if new_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type '{new_type}'. Valid: {', '.join(sorted(VALID_TYPES))}")

    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    models = data.get("models", [])
    normalized = normalize_models_list(models)

    found = False
    for m in normalized:
        if isinstance(m, dict) and m.get("id") == model_id:
            m["type"] = new_type
            found = True
            break

    if not found:
        normalized.append({"id": model_id, "type": new_type})

    data["models"] = normalized
    # Remove old modelTypes key if present (migration from old approach)
    data.pop("modelTypes", None)
    conn.data = json.dumps(data)
    await db.flush()

    return {"ok": True, "model_id": model_id, "type": new_type}
