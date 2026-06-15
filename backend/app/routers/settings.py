"""Application settings endpoints."""

import json
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.settings import SettingsModel
from app.routers.auth import get_current_user
from app.schemas.settings import DatabaseImportRequest, SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

# Default settings values — mirrors original settingsRepo.js DEFAULT_SETTINGS
DEFAULT_SETTINGS = {
    # Auth
    "requireApiKey": False,
    "requireLogin": True,
    "authMode": "password",
    # OIDC
    "oidcIssuerUrl": "",
    "oidcClientId": "",
    # oidcClientSecret stored but never returned in GET
    "oidcScopes": "openid profile email",
    "oidcLoginLabel": "Sign in with OIDC",
    # Cloud/Tunnel
    "cloudEnabled": False,
    "tunnelEnabled": False,
    "tunnelUrl": "",
    "tunnelProvider": "cloudflare",
    "tunnelDashboardAccess": True,
    # Tailscale
    "tailscaleEnabled": False,
    "tailscaleUrl": "",
    # Proxy
    "outboundProxyEnabled": False,
    "outboundProxyUrl": "",
    "outboundNoProxy": "",
    # Routing Strategy
    "comboStrategy": "fallback",
    "stickyRoundRobinLimit": 3,
    "providerStrategies": {},
    "comboStickyRoundRobinLimit": 1,
    "comboStrategies": {},
    # Observability
    "enableObservability": True,
    "observabilityMaxRecords": 1000,
    "observabilityBatchSize": 20,
    "observabilityFlushIntervalMs": 5000,
    "observabilityMaxJsonSize": 5,
    # MITM
    "mitmRouterBaseUrl": "http://localhost:20128",
    # DNS Tool
    "dnsToolEnabled": {},
    # Misc
    "rtkEnabled": True,
    "cavemanEnabled": False,
    "cavemanLevel": "full",
}


async def _get_or_create_settings(db: AsyncSession) -> SettingsModel:
    """Fetch the singleton settings row (id=1), creating it if missing."""
    result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SettingsModel(id=1, data=json.dumps(DEFAULT_SETTINGS))
        db.add(row)
        await db.flush()
        await db.refresh(row)
    return row


def _build_safe_settings(raw: dict) -> dict:
    """Merge with defaults, strip secrets, add runtime flags."""
    merged = {**DEFAULT_SETTINGS, **raw}
    # Remove secrets from response
    merged.pop("oidcClientSecret", None)
    merged.pop("password", None)
    # Computed flags
    merged["oidcConfigured"] = bool(
        merged.get("oidcIssuerUrl") and merged.get("oidcClientId") and raw.get("oidcClientSecret")
    )
    merged["hasPassword"] = bool(raw.get("password"))
    # Runtime flags (env-based, not stored)
    import os
    merged["enableRequestLogs"] = os.environ.get("ENABLE_REQUEST_LOGS", "false").lower() == "true"
    merged["enableTranslator"] = os.environ.get("ENABLE_TRANSLATOR", "false").lower() == "true"
    return merged


@router.get("", response_model=SettingsOut)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return current application settings (secrets excluded)."""
    row = await _get_or_create_settings(db)
    data = json.loads(row.data)
    return SettingsOut(**_build_safe_settings(data))


@router.patch("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Update application settings (partial merge)."""
    row = await _get_or_create_settings(db)
    current = json.loads(row.data)

    update_data = body.model_dump(exclude_unset=True)

    # Handle password change specially
    new_password = update_data.pop("newPassword", None)
    current_password = update_data.pop("currentPassword", None)
    if new_password is not None:
        import bcrypt
        existing_hash = current.get("password", "")
        if existing_hash:
            # Verify current password
            if not current_password:
                raise HTTPException(status_code=400, detail="Current password required")
            if not bcrypt.checkpw(current_password.encode(), existing_hash.encode()):
                raise HTTPException(status_code=401, detail="Invalid current password")
        else:
            # First time — accept default "123456" or empty
            if current_password and current_password != "123456":
                raise HTTPException(status_code=401, detail="Invalid current password")
        current["password"] = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

    # Strip empty oidcClientSecret (don't overwrite with blank)
    if "oidcClientSecret" in update_data:
        if not update_data["oidcClientSecret"] or not str(update_data["oidcClientSecret"]).strip():
            del update_data["oidcClientSecret"]

    current.update(update_data)
    row.data = json.dumps(current)
    await db.flush()
    await db.refresh(row)

    return SettingsOut(**_build_safe_settings(json.loads(row.data)))


# --- Public endpoint: require-login check (no auth required) ---

@router.get("/require-login")
async def check_require_login(db: AsyncSession = Depends(get_db)):
    """Public endpoint for frontend to check if login is required."""
    try:
        row = await _get_or_create_settings(db)
        data = json.loads(row.data)
        return {
            "requireLogin": data.get("requireLogin", True) is not False,
            "tunnelDashboardAccess": data.get("tunnelDashboardAccess", True) is not False,
            "tunnelUrl": data.get("tunnelUrl", ""),
            "tailscaleUrl": data.get("tailscaleUrl", ""),
        }
    except Exception:
        return {"requireLogin": True}


# --- Database export/import ---

DB_TABLES: list[str] = [
    "settings",
    "users",
    "provider_connections",
    "provider_nodes",
    "api_keys",
    "combos",
    "usage_daily",
    "usage_history",
    "request_details",
    "chat_conversations",
    "chat_messages",
    "cli_tool_configs",
    "proxy_pools",
    "mitm_config",
    "mitm_logs",
    "kv",
]


@router.get("/database")
async def export_database(
    db: AsyncSession = Depends(get_db),
    _user: object = Depends(get_current_user),
) -> dict[str, object]:
    """Export all database tables as JSON."""
    result: dict[str, list[dict[str, object]]] = {}
    for table in DB_TABLES:
        rows = (await db.execute(text(f"SELECT * FROM {table}"))).mappings().all()
        result[table] = [dict(r) for r in rows]

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": result,
    }


@router.post("/database")
async def import_database(
    body: DatabaseImportRequest,
    db: AsyncSession = Depends(get_db),
    _user: object = Depends(get_current_user),
) -> dict[str, object]:
    """Import database tables from JSON export. Overwrites existing data."""
    imported: dict[str, int] = {}
    for table in DB_TABLES:
        rows = body.tables.get(table, [])
        if not rows:
            continue
        await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        for row in rows:
            clean = {k: v for k, v in row.items() if v is not None}
            if clean:
                cols = ", ".join(clean.keys())
                placeholders = ", ".join([f":{k}" for k in clean.keys()])
                await db.execute(
                    text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"),
                    clean,
                )
        imported[table] = len(rows)

    await db.commit()
    return {"success": True, "imported": imported}


# --- Proxy test ---

@router.post("/proxy-test")
async def test_proxy(
    db: AsyncSession = Depends(get_db),
    _user: object = Depends(get_current_user),
) -> dict[str, object]:
    """Test the configured outbound proxy by making a request to httpbin."""
    row = await _get_or_create_settings(db)
    data = json.loads(row.data)

    if not data.get("outboundProxyEnabled"):
        raise HTTPException(status_code=400, detail="Outbound proxy is not enabled")

    proxy_url: str = data.get("outboundProxyUrl", "").strip()
    if not proxy_url:
        raise HTTPException(status_code=400, detail="No proxy URL configured")

    start: float = time.monotonic()
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0) as client:
            resp = await client.get("https://httpbin.org/ip")
            elapsed: int = int((time.monotonic() - start) * 1000)
            return {"ok": True, "status": resp.status_code, "elapsedMs": elapsed}
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return {"ok": False, "error": str(e), "elapsedMs": elapsed}
