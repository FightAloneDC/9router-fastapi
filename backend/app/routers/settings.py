"""Application settings endpoints."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.settings import SettingsModel
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.settings import DatabaseImportRequest, SettingsOut, SettingsUpdate
from app.services.auth import get_any_user, hash_password, verify_password
from app.routers.providers.connection_filters import ConnectionListFilters
from app.services.database_transfer import (
    CONNECTIONS_TABLES,
    IMPORT_MODE_MERGE,
    IMPORT_MODE_REPLACE,
    IMPORT_ORDER,
    ConnectionExportOptions,
    build_export_payload,
    export_connections_filtered,
    export_options_to_filters_dict,
    export_tables,
    import_connections_data,
    import_tables,
)

BACKUP_DIR = Path("backups")

_DATETIME_FMTS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def _parse_datetimes(rows: list[dict]) -> list[dict]:
    """Convert ISO datetime strings to datetime objects for asyncpg."""
    out = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if isinstance(v, str) and len(v) > 10:
                for fmt in _DATETIME_FMTS:
                    try:
                        v = datetime.strptime(v, fmt)
                        break
                    except ValueError:
                        continue
            clean[k] = v
        out.append(clean)
    return out

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
    # Runtime flags (env-based, not stored)
    import os
    merged["enableRequestLogs"] = os.environ.get("ENABLE_REQUEST_LOGS", "false").lower() == "true"
    merged["enableTranslator"] = os.environ.get("ENABLE_TRANSLATOR", "false").lower() == "true"
    return merged


async def _settings_response(db: AsyncSession, raw: dict) -> SettingsOut:
    """Build settings response with auth flags from users table."""
    safe = _build_safe_settings(raw)
    safe["hasPassword"] = await get_any_user(db) is not None
    return SettingsOut(**safe)


@router.get("", response_model=SettingsOut)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return current application settings (secrets excluded)."""
    row = await _get_or_create_settings(db)
    data = json.loads(row.data)
    return await _settings_response(db, data)


@router.patch("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update application settings (partial merge)."""
    row = await _get_or_create_settings(db)
    current = json.loads(row.data)

    update_data = body.model_dump(exclude_unset=True)

    # Handle password change — login uses users.hashed_password, not settings JSON
    new_password = update_data.pop("newPassword", None)
    current_password = update_data.pop("currentPassword", None)
    if new_password is not None:
        if not current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password required",
            )
        if not verify_password(current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid current password",
            )
        current_user.hashed_password = hash_password(new_password)
        current.pop("password", None)

    # Strip empty oidcClientSecret (don't overwrite with blank)
    if "oidcClientSecret" in update_data:
        if not update_data["oidcClientSecret"] or not str(update_data["oidcClientSecret"]).strip():
            del update_data["oidcClientSecret"]

    current.update(update_data)
    row.data = json.dumps(current)
    await db.flush()
    await db.refresh(row)

    return await _settings_response(db, json.loads(row.data))


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


async def _auto_backup_before_import(
    db: AsyncSession,
    prefix: str,
) -> Path:
    """Snapshot current DB tables before a destructive import."""
    backup_data = await export_tables(db, IMPORT_ORDER)
    backup_dir = BACKUP_DIR.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{prefix}-{stamp}.json"
    backup_path.write_text(
        json.dumps(
            build_export_payload(backup_data, scope="auto-backup"),
            indent=2,
            default=str,
        )
    )
    return backup_path


@router.get("/database")
async def export_database(
    db: AsyncSession = Depends(get_db),
    _user: object = Depends(get_current_user),
) -> dict[str, object]:
    """Export all application tables as JSON (FK-safe metadata)."""
    tables = await export_tables(db, IMPORT_ORDER)
    return build_export_payload(tables, scope="full")


@router.post("/database")
async def import_database(
    body: DatabaseImportRequest,
    db: AsyncSession = Depends(get_db),
    _user: object = Depends(get_current_user),
) -> dict[str, object]:
    """Import full database export. Restores rows verbatim, not bulk-add."""
    backup_path = await _auto_backup_before_import(db, "auto-pre-import")
    imported = await import_tables(
        db,
        body.tables,
        IMPORT_ORDER,
        _parse_datetimes,
    )
    await db.commit()
    return {"success": True, "imported": imported, "backup": str(backup_path)}


@router.get("/database/connections")
async def export_connections(
    db: AsyncSession = Depends(get_db),
    _user: object = Depends(get_current_user),
    providers: str | None = Query(
        None,
        description="Comma-separated provider ids",
    ),
    is_active: bool | None = Query(None),
    test_status: str | None = Query(None),
    health: str | None = Query(
        None,
        description="healthy, rate_limited, cooldown, exhausted, dead",
    ),
    auth_type: str | None = Query(None),
    has_proxy: bool | None = Query(None),
    in_cooldown: bool | None = Query(None),
    token_issue: str | None = Query(
        None,
        pattern="^(expired|refresh_error|any)$",
    ),
    q: str | None = Query(None),
    include_catalog: bool = Query(True),
    include_quota: bool = Query(True),
) -> dict[str, object]:
    """Export connections with optional filters (selective export)."""
    provider_list: list[str] | None = None
    if providers:
        provider_list = [p.strip() for p in providers.split(",") if p.strip()]

    filters = ConnectionListFilters(
        q=q,
        is_active=is_active,
        test_status=test_status,
        auth_type=auth_type,
        has_proxy=has_proxy,
        in_cooldown=in_cooldown,
        token_issue=token_issue,  # type: ignore[arg-type]
    )
    options = ConnectionExportOptions(
        providers=provider_list,
        filters=filters,
        health=health,
        include_catalog=include_catalog,
        include_quota=include_quota,
    )

    try:
        tables = await export_connections_filtered(db, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    scope = "connections-selective" if (
        provider_list
        or health
        or is_active is not None
        or test_status
        or auth_type
        or has_proxy is not None
        or in_cooldown is not None
        or token_issue
        or (q and q.strip())
    ) else "connections"

    import_mode = IMPORT_MODE_MERGE if provider_list else IMPORT_MODE_REPLACE
    filter_payload = export_options_to_filters_dict(options)

    return build_export_payload(
        tables,
        scope=scope,
        filters=filter_payload,
        import_mode=import_mode,
    )


@router.post("/database/connections")
async def import_connections(
    body: DatabaseImportRequest,
    db: AsyncSession = Depends(get_db),
    _user: object = Depends(get_current_user),
    import_mode: str | None = Query(
        None,
        description="replace_all or merge_providers",
    ),
) -> dict[str, object]:
    """Import connections export without touching auth, settings, or usage."""
    backup_path = await _auto_backup_before_import(db, "auto-pre-connections-import")
    mode = import_mode or body.import_mode or IMPORT_MODE_REPLACE
    if mode not in (IMPORT_MODE_REPLACE, IMPORT_MODE_MERGE):
        raise HTTPException(
            status_code=400,
            detail="import_mode must be replace_all or merge_providers",
        )
    imported = await import_connections_data(
        db,
        body.tables,
        _parse_datetimes,
        import_mode=mode,
        filters=body.filters,
    )
    await db.commit()
    return {
        "success": True,
        "imported": imported,
        "import_mode": mode,
        "backup": str(backup_path),
    }


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
