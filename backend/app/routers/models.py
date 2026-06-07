"""Model availability and cooldown endpoints."""

import json
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.models.settings import SettingsModel
from app.routers.auth import get_current_user

router = APIRouter(prefix="/models", tags=["models"])

MODEL_LOCK_PREFIX = "modelLock_"


def _get_active_locks(data: dict) -> list[dict]:
    """Extract active model locks from connection data."""
    now = datetime.now(timezone.utc)
    locks = []
    for key, value in data.items():
        if key.startswith(MODEL_LOCK_PREFIX) and value:
            try:
                until = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if until > now:
                    locks.append({
                        "model": key[len(MODEL_LOCK_PREFIX):] or "__all",
                        "until": value,
                    })
            except (ValueError, TypeError):
                continue
    return locks


@router.get("/availability")
async def get_model_availability(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get model availability status across all connections."""
    result = await db.execute(select(ProviderConnection))
    connections = result.scalars().all()

    models = []
    for conn in connections:
        import json
        data = json.loads(conn.data) if conn.data else {}

        locks = _get_active_locks(data)
        for lock in locks:
            models.append({
                "provider": conn.provider,
                "model": lock["model"],
                "status": "cooldown",
                "until": lock["until"],
                "connectionId": str(conn.id),
                "connectionName": conn.name or conn.email or str(conn.id),
                "lastError": data.get("lastError"),
            })

        if not locks and data.get("testStatus") == "unavailable":
            models.append({
                "provider": conn.provider,
                "model": "__all",
                "status": "unavailable",
                "connectionId": str(conn.id),
                "connectionName": conn.name or conn.email or str(conn.id),
                "lastError": data.get("lastError"),
            })

    return {
        "models": models,
        "unavailableCount": len(models),
    }


class ClearCooldownRequest(BaseModel):
    action: str
    provider: str
    model: str


@router.post("/availability")
async def clear_model_cooldown(
    body: ClearCooldownRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Clear model cooldown for a specific provider/model."""
    if body.action != "clearCooldown":
        raise HTTPException(status_code=400, detail="Invalid action")

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.provider == body.provider)
    )
    connections = result.scalars().all()

    lock_key = f"{MODEL_LOCK_PREFIX}{body.model}"

    for conn in connections:
        import json
        data = json.loads(conn.data) if conn.data else {}
        if lock_key in data:
            data.pop(lock_key, None)
            if data.get("testStatus") == "unavailable":
                data["testStatus"] = "active"
                data["lastError"] = None
                data["lastErrorAt"] = None
                data["backoffLevel"] = 0
            conn.data = json.dumps(data)

    await db.flush()
    return {"ok": True}


# ── Helpers for settings-based storage ─────────────────────────────

async def _get_settings_data(db: AsyncSession) -> dict:
    """Get the settings data blob."""
    result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        return {}
    try:
        return json.loads(row.data) if row.data else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def _save_settings_data(db: AsyncSession, data: dict):
    """Save the settings data blob."""
    result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SettingsModel(id=1, data=json.dumps(data))
        db.add(row)
    else:
        row.data = json.dumps(data)
    await db.flush()


# ── Model Aliases ─────────────────────────────────────────────────

@router.get("/alias")
async def get_model_aliases(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get all model aliases."""
    data = await _get_settings_data(db)
    return {"aliases": data.get("modelAliases", {})}


class SetAliasRequest(BaseModel):
    model: str
    alias: str


@router.put("/alias")
async def set_model_alias(
    body: SetAliasRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Set a model alias."""
    if not body.model or not body.alias:
        raise HTTPException(status_code=400, detail="Model and alias required")
    data = await _get_settings_data(db)
    aliases = data.get("modelAliases", {})
    aliases[body.alias] = body.model
    data["modelAliases"] = aliases
    await _save_settings_data(db, data)
    return {"success": True, "model": body.model, "alias": body.alias}


@router.delete("/alias")
async def delete_model_alias(
    alias: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delete a model alias."""
    if not alias:
        raise HTTPException(status_code=400, detail="Alias required")
    data = await _get_settings_data(db)
    aliases = data.get("modelAliases", {})
    aliases.pop(alias, None)
    data["modelAliases"] = aliases
    await _save_settings_data(db, data)
    return {"success": True}


# ── Disabled Models ───────────────────────────────────────────────

@router.get("/disabled")
async def get_disabled_models(
    providerAlias: str = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get disabled models, optionally filtered by provider alias."""
    data = await _get_settings_data(db)
    all_disabled = data.get("disabledModels", {})
    if providerAlias:
        return {"ids": all_disabled.get(providerAlias, [])}
    return {"disabled": all_disabled}


class DisableModelsRequest(BaseModel):
    providerAlias: str
    ids: list[str]


@router.post("/disabled")
async def disable_models(
    body: DisableModelsRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Disable models for a provider."""
    if not body.providerAlias or not isinstance(body.ids, list):
        raise HTTPException(status_code=400, detail="providerAlias and ids[] required")
    data = await _get_settings_data(db)
    disabled = data.get("disabledModels", {})
    existing = set(disabled.get(body.providerAlias, []))
    existing.update(body.ids)
    disabled[body.providerAlias] = list(existing)
    data["disabledModels"] = disabled
    await _save_settings_data(db, data)
    return {"success": True}


@router.delete("/disabled")
async def enable_models(
    providerAlias: str = None,
    id: str = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Enable models (remove from disabled list).
    
    - If both providerAlias and id are given: enable single model
    - If only providerAlias: enable all models for that provider
    """
    if not providerAlias:
        raise HTTPException(status_code=400, detail="providerAlias required")
    data = await _get_settings_data(db)
    disabled = data.get("disabledModels", {})
    if id:
        # Remove single model
        current = disabled.get(providerAlias, [])
        disabled[providerAlias] = [m for m in current if m != id]
        if not disabled[providerAlias]:
            del disabled[providerAlias]
    else:
        # Remove all for provider
        disabled.pop(providerAlias, None)
    data["disabledModels"] = disabled
    await _save_settings_data(db, data)
    return {"success": True}


# ── Model Test ────────────────────────────────────────────────────

class TestModelRequest(BaseModel):
    model: str
    kind: str = "chat"


@router.post("/test")
async def test_model(
    body: TestModelRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Test a model by making a minimal completions call directly to the upstream provider.
    
    Resolves the model to a provider target and calls the upstream API directly,
    instead of going through the internal proxy (which fails in Docker due to port mismatch).
    """
    if not body.model:
        raise HTTPException(status_code=400, detail="Model required")

    # Resolve model to upstream target directly
    from app.services.proxy import resolve_model_to_targets
    targets = await resolve_model_to_targets(db, body.model)
    if not targets:
        # Parse the model string to give a more helpful error
        if "/" in body.model:
            provider_part = body.model.split("/", 1)[0]
            return {"ok": False, "error": f"No active connection found for provider '{provider_part}'. Please add a connection in the provider settings.", "latencyMs": 0}
        return {"ok": False, "error": f"No active provider connection found to test model '{body.model}'.", "latencyMs": 0}

    target = targets[0]
    url = target.url
    headers = target.headers

    start = time.time()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if body.kind == "embedding":
                # For embeddings, use the embeddings endpoint
                cfg_url = url.replace("/chat/completions", "/embeddings")
                resp = await client.post(
                    cfg_url,
                    headers=headers,
                    json={"model": target.model, "input": "test"},
                )
            elif target.provider == "qoder":
                # Qoder needs WAF-bypass encoding + COSY signing
                # Qoder returns SSE streams even for non-streaming requests,
                # so we must stream-read and parse incrementally.
                from app.services.proxy import build_qoder_request

                test_body = {
                    "model": target.model,
                    "max_tokens": 1,
                    "stream": False,
                    "messages": [{"role": "user", "content": "hi"}],
                }

                # Look up connection data for credentials
                conn_data = {}
                if target.connection_id:
                    conn_result = await db.execute(
                        select(ProviderConnection).where(
                            ProviderConnection.id == target.connection_id
                        )
                    )
                    conn = conn_result.scalar_one_or_none()
                    if conn and conn.data:
                        conn_data = json.loads(conn.data)

                raw_body, qoder_headers = await build_qoder_request(
                    target, test_body, conn_data
                )


                # Stream-read the SSE response to avoid timeout
                # Qoder returns HTTP 200 even for errors, embedding the real status
                # in the SSE envelope as statusCodeValue
                qoder_ok = False
                qoder_status = 0
                qoder_error = None
                async with client.stream("POST", url, headers=qoder_headers, content=raw_body) as resp:
                    qoder_status = resp.status_code
                    if resp.status_code >= 400:
                        error_body = b""
                        async for chunk in resp.aiter_bytes():
                            error_body += chunk
                            if len(error_body) > 2000:
                                break
                        latency_ms = int((time.time() - start) * 1000)
                        return {"ok": False, "latencyMs": latency_ms, "error": f"Qoder HTTP {resp.status_code}: {error_body.decode(errors='replace')[:240]}", "status": resp.status_code}
                    line_buf = ""
                    async for raw_chunk in resp.aiter_text():
                        line_buf += raw_chunk
                        while "\n" in line_buf:
                            line, line_buf = line_buf.split("\n", 1)
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            payload = line[5:].strip()
                            if payload == "[DONE]":
                                break
                            if not payload:
                                continue
                            try:
                                envelope = json.loads(payload)
                            except (json.JSONDecodeError, TypeError):
                                continue
                            # Check for Qoder error in SSE envelope
                            sse_status = envelope.get("statusCodeValue", 0)
                            if sse_status and sse_status >= 400:
                                err_body = envelope.get("body", "")
                                try:
                                    err_obj = json.loads(err_body) if isinstance(err_body, str) else err_body
                                    qoder_error = f"Qoder {sse_status} ({envelope.get('statusCode', '')}): code={err_obj.get('code', '?')} {str(err_obj.get('message', ''))[:200]}"
                                except (json.JSONDecodeError, TypeError):
                                    qoder_error = f"Qoder {sse_status}: {str(err_body)[:200]}"
                                break
                            inner = envelope.get("body", "")
                            if not inner:
                                continue
                            try:
                                chunk_data = json.loads(inner)
                            except (json.JSONDecodeError, TypeError):
                                continue
                            choices = chunk_data.get("choices", [])
                            if choices:
                                qoder_ok = True
                        if qoder_ok or qoder_error:
                            break

                latency_ms = int((time.time() - start) * 1000)
                if qoder_ok:
                    return {"ok": True, "latencyMs": latency_ms, "error": None, "status": qoder_status}
                elif qoder_error:
                    return {"ok": False, "latencyMs": latency_ms, "status": qoder_status, "error": qoder_error}
                else:
                    return {"ok": False, "latencyMs": latency_ms, "status": qoder_status, "error": "Qoder returned no completion choices (timeout or empty response)"}

            else:
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

        latency_ms = int((time.time() - start) * 1000)
        raw_text = resp.text

        try:
            parsed = json.loads(raw_text) if raw_text else None
        except (json.JSONDecodeError, TypeError):
            parsed = None

        if resp.status_code >= 400:
            detail = ""
            if parsed:
                detail = (
                    parsed.get("error", {}).get("message", "")
                    if isinstance(parsed.get("error"), dict)
                    else str(parsed.get("error", ""))
                )
            error = f"HTTP {resp.status_code}{': ' + detail[:240] if detail else ''}"
            return {"ok": False, "latencyMs": latency_ms, "error": error, "status": resp.status_code}

        # Check for provider-level errors
        if parsed and parsed.get("error"):
            provider_error = parsed["error"]
            if isinstance(provider_error, dict):
                provider_error = provider_error.get("message", "Provider returned an error")
            return {"ok": False, "latencyMs": latency_ms, "status": resp.status_code, "error": str(provider_error)[:240]}

        # For chat completions, check for choices (OpenAI) or candidates (Gemini)
        if body.kind != "embedding":
            has_choices = isinstance(parsed, dict) and (
                (isinstance(parsed.get("choices"), list) and len(parsed["choices"]) > 0)
                or (isinstance(parsed.get("candidates"), list) and len(parsed["candidates"]) > 0)
            )
            if not has_choices:
                return {"ok": False, "latencyMs": latency_ms, "status": resp.status_code, "error": "Provider returned no completion choices"}
        else:
            has_data = isinstance(parsed, dict) and isinstance(parsed.get("data"), list) and len(parsed["data"]) > 0
            if not has_data:
                return {"ok": False, "latencyMs": latency_ms, "status": resp.status_code, "error": "Provider returned no embedding data"}

        return {"ok": True, "latencyMs": latency_ms, "error": None, "status": resp.status_code}

    except httpx.TimeoutException:
        return {"ok": False, "error": "Request timed out (60s)", "latencyMs": 60000}
    except httpx.ConnectError:
        return {"ok": False, "error": f"Cannot connect to {target.provider} at {url}. Check the base URL and network connectivity.", "latencyMs": 0}
    except Exception as e:
        return {"ok": False, "error": str(e)[:240], "latencyMs": 0}
