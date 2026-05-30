"""Provider connection testing and batch test endpoints."""

import asyncio
import json
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.constants import PROVIDER_DEFAULTS, infer_model_type
from app.routers.providers.helpers import _get_base_url, _get_validation_type
from app.routers.providers.validation import (
    _validate_anthropic,
    _validate_assemblyai,
    _validate_azure,
    _validate_cloudflare,
    _validate_deepgram,
    _validate_elevenlabs,
    _validate_google,
    _validate_inworld,
    _validate_minimax,
    _validate_noauth,
    _validate_ollama,
    _validate_openai_chat,
    _validate_openai_compatible,
    _validate_vertex,
    _validate_voyage,
)
from app.schemas.provider import (
    BatchTestRequest,
    BatchTestResponse,
    BatchTestResult,
    ProviderTestResponse,
    ProviderValidateRequest,
    ProviderValidateResponse,
)


async def _test_openai_compatible(api_key: str, base_url: str) -> dict:
    """Test an OpenAI-compatible provider connection and return models if available."""
    if not api_key:
        return {"valid": False, "error": "No API key configured for this connection", "latencyMs": 0, "models": None}
    start = time.monotonic()
    url = f"{base_url.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            latency = int((time.monotonic() - start) * 1000)
            valid = resp.status_code < 400
            error = None if valid else f"HTTP {resp.status_code}"
            models = []
            if valid:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        models = [
                            {"id": m["id"], "type": infer_model_type(m["id"])}
                            for m in data["data"] if m.get("id")
                        ]
                except Exception:
                    pass
            return {"valid": valid, "error": error, "latencyMs": latency, "models": models or None}
        except httpx.ConnectError:
            return {"valid": False, "error": f"Cannot connect to {base_url}", "latencyMs": int((time.monotonic() - start) * 1000), "models": None}
        except httpx.TimeoutException:
            return {"valid": False, "error": "Connection timed out", "latencyMs": int((time.monotonic() - start) * 1000), "models": None}
        except Exception as e:
            return {"valid": False, "error": str(e)[:200], "latencyMs": int((time.monotonic() - start) * 1000), "models": None}


async def _test_anthropic_compatible(api_key: str, base_url: str) -> dict:
    """Test an Anthropic-compatible provider connection and return models if available."""
    if not api_key:
        return {"valid": False, "error": "No API key configured for this connection", "latencyMs": 0, "models": None}
    start = time.monotonic()
    normalized = base_url.rstrip("/")
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
            latency = int((time.monotonic() - start) * 1000)
            valid = resp.status_code < 400
            error = None if valid else f"HTTP {resp.status_code}"
            models = []
            if valid:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        models = [
                            {"id": m["id"], "type": infer_model_type(m["id"])}
                            for m in data["data"] if m.get("id")
                        ]
                except Exception:
                    pass
            return {"valid": valid, "error": error, "latencyMs": latency, "models": models or None}
        except Exception as e:
            return {"valid": False, "error": str(e)[:200], "latencyMs": int((time.monotonic() - start) * 1000), "models": None}


async def _test_provider_connection(conn: ProviderConnection, db: AsyncSession) -> dict:
    """Test a single provider connection and return result dict.

    Handles OpenAI-compatible, Anthropic-compatible, and specific known providers.
    """
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key = data.get("apiKey", "")
    provider = conn.provider
    base_url = _get_base_url(provider, None, data)

    # Determine if this is a compatible provider (node-based)
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
        node_type = node.type

        if node_type == "openai-compatible":
            if node_base_url:
                return await _test_openai_compatible(api_key, node_base_url)
        elif node_type == "anthropic-compatible":
            if node_base_url:
                return await _test_anthropic_compatible(api_key, node_base_url)

    # Provider-specific validation — require credentials
    if not api_key and not data.get("accessToken", ""):
        return {"valid": False, "error": "No API key configured for this connection", "latencyMs": 0, "models": None}

    vtype = _get_validation_type(provider)

    if vtype == "anthropic":
        result = await _validate_anthropic(api_key, base_url)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype == "google":
        result = await _validate_google(api_key)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype == "azure":
        result = await _validate_azure(api_key, data)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": None}

    if provider in ("ollama", "ollama-local"):
        url = base_url or "http://localhost:11434"
        result = await _validate_ollama(url)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if provider == "vertex":
        result = await _validate_vertex(api_key)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": None}

    if vtype == "openai-chat":
        result = await _validate_openai_chat(api_key, base_url)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    # ── Media providers (TTS / STT / embedding) ──────────────────────
    if vtype == "noauth":
        result = _validate_noauth()
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype == "elevenlabs":
        result = await _validate_elevenlabs(api_key)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype == "deepgram":
        result = await _validate_deepgram(api_key)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype == "inworld":
        result = await _validate_inworld(api_key)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype == "voyage":
        result = await _validate_voyage(api_key)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype == "assemblyai":
        result = await _validate_assemblyai(api_key)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    if vtype in ("minimax", "minimax-cn"):
        result = await _validate_minimax(api_key, vtype)
        return {"valid": result.valid, "error": result.error, "latencyMs": 0, "models": result.models}

    # Default: OpenAI-compatible validation
    if base_url:
        vr = await _validate_openai_compatible(api_key, base_url)
        return {"valid": vr.valid, "error": vr.error, "latencyMs": 0, "models": vr.models}

    # Try from defaults
    default_url = PROVIDER_DEFAULTS.get(provider, {}).get("baseUrl", "")
    if default_url:
        vr = await _validate_openai_compatible(api_key, default_url)
        return {"valid": vr.valid, "error": vr.error, "latencyMs": 0, "models": vr.models}

    return {"valid": False, "error": f"Provider {provider} does not support connection testing", "latencyMs": 0, "models": None}


# --- Endpoints ---


@router.post("/providers/validate", response_model=ProviderValidateResponse)
async def validate_provider(
    body: ProviderValidateRequest,
    _user=Depends(get_current_user),
):
    """Validate provider credentials by making a test API call."""
    extra = body.providerSpecificData or {}
    vtype = _get_validation_type(body.provider)

    if vtype == "anthropic":
        if not body.apiKey:
            return ProviderValidateResponse(valid=False, error="API key is required for Anthropic")
        return await _validate_anthropic(body.apiKey, extra.get("baseUrl"))

    if vtype == "google":
        if not body.apiKey:
            return ProviderValidateResponse(valid=False, error="API key is required for Google")
        return await _validate_google(body.apiKey)

    if vtype == "azure":
        return await _validate_azure(body.apiKey, extra)

    if vtype == "cloudflare":
        return await _validate_cloudflare(body.apiKey, extra)

    if vtype == "openai-chat":
        if not body.apiKey:
            return ProviderValidateResponse(valid=False, error="API key is required for Kilo Gateway")
        base_url = _get_base_url(body.provider, body.baseUrl, extra)
        if not base_url:
            return ProviderValidateResponse(valid=False, error="Base URL is required")
        return await _validate_openai_chat(body.apiKey, base_url)

    if vtype == "vertex":
        if not body.apiKey:
            return ProviderValidateResponse(valid=False, error="API key or service account JSON is required")
        return await _validate_vertex(body.apiKey)

    if vtype == "cookie":
        return ProviderValidateResponse(valid=False, error="Cookie-based providers require manual cookie validation — paste your cookie and test at usage time")

    # ── Media providers (TTS / STT / embedding) ──────────────────────
    if vtype == "noauth":
        return _validate_noauth()

    if vtype == "elevenlabs":
        return await _validate_elevenlabs(body.apiKey)

    if vtype == "deepgram":
        return await _validate_deepgram(body.apiKey)

    if vtype == "inworld":
        return await _validate_inworld(body.apiKey)

    if vtype == "voyage":
        return await _validate_voyage(body.apiKey)

    if vtype == "assemblyai":
        return await _validate_assemblyai(body.apiKey)

    if vtype in ("minimax", "minimax-cn"):
        return await _validate_minimax(body.apiKey, vtype)

    if body.provider in ("ollama", "ollama-local"):
        base_url = _get_base_url(body.provider, body.baseUrl, extra)
        return await _validate_ollama(base_url)

    # OpenAI-compatible (default)
    if not body.apiKey:
        return ProviderValidateResponse(valid=False, error="API key is required")
    base_url = _get_base_url(body.provider, body.baseUrl, extra)
    if not base_url:
        return ProviderValidateResponse(valid=False, error="Base URL is required")

    # Build extra headers if needed (e.g. OpenRouter)
    extra_headers = {}
    if extra.get("httpReferer"):
        extra_headers["HTTP-Referer"] = extra["httpReferer"]
    if extra.get("xTitle"):
        extra_headers["X-Title"] = extra["xTitle"]

    return await _validate_openai_compatible(body.apiKey, base_url, extra_headers)


@router.post("/providers/test-batch", response_model=BatchTestResponse)
async def test_batch(
    body: BatchTestRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Test multiple provider connections by group (mode: provider, apikey, all)."""
    if not body.mode:
        raise HTTPException(status_code=400, detail="mode is required")

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.is_active == True)
    )
    all_connections = result.scalars().all()

    if body.mode == "provider" and body.providerId:
        connections_to_test = [c for c in all_connections if c.provider == body.providerId]
    elif body.mode == "apikey":
        connections_to_test = [c for c in all_connections if c.auth_type != "oauth"]
    elif body.mode == "all":
        connections_to_test = list(all_connections)
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid mode. Use: provider, apikey, all",
        )

    if not connections_to_test:
        return BatchTestResponse(
            mode=body.mode,
            providerId=body.providerId,
            results=[],
            summary={"total": 0, "passed": 0, "failed": 0},
            testedAt=datetime.now(timezone.utc).isoformat(),
        )

    results = []
    for conn in connections_to_test:
        try:
            test_result = await _test_provider_connection(conn, db)
            results.append(BatchTestResult(
                provider=conn.provider,
                connectionId=str(conn.id),
                connectionName=conn.name or conn.provider,
                authType=conn.auth_type,
                valid=test_result["valid"],
                latencyMs=test_result.get("latencyMs", 0),
                error=test_result.get("error"),
                testedAt=datetime.now(timezone.utc).isoformat(),
            ))
        except Exception as e:
            results.append(BatchTestResult(
                provider=conn.provider,
                connectionId=str(conn.id),
                connectionName=conn.name or conn.provider,
                authType=conn.auth_type,
                valid=False,
                latencyMs=0,
                error=str(e)[:200],
                testedAt=datetime.now(timezone.utc).isoformat(),
            ))

    return BatchTestResponse(
        mode=body.mode,
        providerId=body.providerId,
        results=results,
        testedAt=datetime.now(timezone.utc).isoformat(),
        summary={
            "total": len(results),
            "passed": sum(1 for r in results if r.valid),
            "failed": sum(1 for r in results if not r.valid),
        },
    )


class TestModelsRequest(BaseModel):
    """Request body for testing all models of a provider connection."""
    pass


@router.post("/providers/{connection_id}/test-models")
async def test_connection_models(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Test all models of a provider connection by making minimal chat completion calls.

    Fetches the model list for the provider, then pings each model with a simple request.
    Returns per-model results with latency and error info.
    """
    from app.services.proxy import resolve_model_to_target, build_upstream_request
    from app.routers.providers.constants import PROVIDER_CONFIGS

    # Get the connection
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    provider_id = conn.provider
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key = data.get("apiKey", "")
    alias = data.get("alias", provider_id)

    # Get models from the provider's stored models
    from app.routers.providers.models import get_provider_models
    models = await get_provider_models(db, provider_id, alias)

    if not models:
        return {
            "provider": provider_id,
            "connectionId": connection_id,
            "results": [],
            "error": "No models configured for this provider",
        }

    # Ping each model
    async def ping_model(model_id: str) -> dict:
        """Test a single model via the internal test endpoint."""
        start = time.monotonic()
        try:
            # Use the existing test_model logic via resolve_model_to_target
            targets = await resolve_model_to_target(db, f"{alias}/{model_id}")
            if not targets:
                return {
                    "modelId": model_id,
                    "ok": False,
                    "latencyMs": int((time.monotonic() - start) * 1000),
                    "error": f"No active connection found for model '{model_id}'",
                }

            target = targets[0]
            url = target.url
            headers = target.headers

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": target.model,
                        "max_tokens": 1,
                        "stream": False,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                latency = int((time.monotonic() - start) * 1000)
                # 200 = working; 400 = bad request but auth passed (model reachable)
                ok = resp.status_code in (200, 400)
                error = None if ok else f"HTTP {resp.status_code}"
                if not ok:
                    try:
                        err_data = resp.json()
                        error = err_data.get("error", {}).get("message", error)
                    except Exception:
                        pass
                return {"modelId": model_id, "ok": ok, "latencyMs": latency, "error": error}
        except httpx.TimeoutException:
            return {"modelId": model_id, "ok": False, "latencyMs": int((time.monotonic() - start) * 1000), "error": "Timeout"}
        except httpx.ConnectError:
            return {"modelId": model_id, "ok": False, "latencyMs": int((time.monotonic() - start) * 1000), "error": "Connection failed"}
        except Exception as e:
            return {"modelId": model_id, "ok": False, "latencyMs": int((time.monotonic() - start) * 1000), "error": str(e)[:200]}

    # Ping first model alone (warm up for token refresh), then rest in parallel
    model_ids = [m if isinstance(m, str) else m.get("id", "") for m in models]
    model_ids = [m for m in model_ids if m]

    if not model_ids:
        return {
            "provider": provider_id,
            "connectionId": connection_id,
            "results": [],
            "error": "No valid model IDs found",
        }

    first_result = await ping_model(model_ids[0])
    results = [first_result]

    if len(model_ids) > 1:
        rest_results = await asyncio.gather(*[ping_model(m) for m in model_ids[1:]])
        results.extend(rest_results)

    return {
        "provider": provider_id,
        "connectionId": connection_id,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("ok")),
            "failed": sum(1 for r in results if not r.get("ok")),
        },
    }
