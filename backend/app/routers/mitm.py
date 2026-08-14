"""MITM proxy management endpoints."""

import json
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mitm import MitmConfig, MitmLog
from app.routers.auth import get_current_user
from app.schemas.mitm import MitmConfigOut, MitmConfigUpdate, MitmLogOut
from app.services.mitm.cert import generate_root_ca
from app.services.mitm.hosts import apply_dns
from app.services.mitm.paths import CA_CERT, DEFAULT_ROUTER_BASE, cert_files_exist
from app.services.mitm.process import (
    get_runtime_status,
    start_mitm_process,
    stop_mitm_process,
)

router = APIRouter(prefix="/mitm", tags=["mitm"])

_INGEST_TOKEN = secrets.token_hex(16)

# Default tools configuration
DEFAULT_TOOLS_CONFIG: dict = {
    "antigravity": {"dnsEnabled": False, "modelMappings": {}},
    "copilot": {"dnsEnabled": False, "modelMappings": {}},
    "kiro": {"dnsEnabled": False, "modelMappings": {}},
    "cursor": {"dnsEnabled": False, "modelMappings": {}},
}


async def _get_or_create_config(db: AsyncSession) -> MitmConfig:
    """Fetch the singleton MITM config row (id=1), creating it if missing."""
    result = await db.execute(select(MitmConfig).where(MitmConfig.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = MitmConfig(
            id=1,
            router_base_url=DEFAULT_ROUTER_BASE,
            tools_config=json.dumps(DEFAULT_TOOLS_CONFIG),
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
    return row


@router.get("/config", response_model=MitmConfigOut)
async def get_config(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return current MITM proxy configuration."""
    row = await _get_or_create_config(db)
    return MitmConfigOut.model_validate(row)


@router.patch("/config", response_model=MitmConfigOut)
async def update_config(
    body: MitmConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Partially update MITM proxy configuration."""
    row = await _get_or_create_config(db)
    update_data = body.model_dump(exclude_unset=True)

    # Serialize tools_config to JSON string if provided
    if "tools_config" in update_data:
        update_data["tools_config"] = json.dumps(update_data["tools_config"])

    for field, value in update_data.items():
        setattr(row, field, value)

    if "tools_config" in update_data:
        try:
            tools = json.loads(row.tools_config)
        except json.JSONDecodeError:
            tools = {}
        for tool, cfg in tools.items():
            if not isinstance(cfg, dict):
                continue
            try:
                apply_dns(tool, bool(cfg.get("dnsEnabled")))
            except OSError:
                pass

    await db.flush()
    await db.refresh(row)
    return MitmConfigOut.model_validate(row)


def _ingest_base() -> str:
    port = os.environ.get("PORT") or os.environ.get("UVICORN_PORT") or "9000"
    return f"http://127.0.0.1:{port}/mitm/internal/log"


@router.post("/start")
async def start_mitm(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Start the MITM HTTPS listener and persist enabled=true on success."""
    row = await _get_or_create_config(db)
    try:
        runtime = start_mitm_process(
            port=row.port,
            router_base_url=row.router_base_url or DEFAULT_ROUTER_BASE,
            ingest_url=_ingest_base(),
            ingest_token=_INGEST_TOKEN,
        )
    except RuntimeError as exc:
        row.enabled = False
        await db.flush()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    row.enabled = True
    row.cert_generated = bool(runtime.get("certExists"))
    await db.flush()
    return {
        "status": "started",
        "message": "MITM proxy is listening",
        **runtime,
    }


@router.post("/stop")
async def stop_mitm(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Stop the MITM child process."""
    row = await _get_or_create_config(db)
    stop_mitm_process()
    row.enabled = False
    await db.flush()
    return {"status": "stopped", "message": "MITM proxy stopped"}


@router.post("/generate-cert")
async def generate_cert(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Write a real Root CA under .scratch/mitm/."""
    row = await _get_or_create_config(db)
    path = generate_root_ca(force=True)
    row.cert_generated = True
    await db.flush()
    return {
        "status": "generated",
        "message": "SSL certificate generated successfully",
        "certPath": str(path),
    }


@router.get("/cert")
async def download_cert(
    _user=Depends(get_current_user),
):
    """Download the MITM Root CA (for host / client trust)."""
    if not cert_files_exist():
        raise HTTPException(
            status_code=404,
            detail="Certificate not generated yet",
        )
    return FileResponse(
        path=CA_CERT,
        media_type="application/x-x509-ca-cert",
        filename="9router-mitm-rootCA.crt",
    )


@router.get("/status")
async def get_status(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Runtime status from process + cert files + /etc/hosts."""
    row = await _get_or_create_config(db)
    runtime = get_runtime_status(row.port)
    row.enabled = bool(runtime["running"])
    row.cert_generated = bool(runtime["certExists"])
    await db.flush()
    return runtime


@router.post("/internal/log")
async def ingest_log(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_mitm_token: str | None = Header(default=None, alias="X-Mitm-Token"),
):
    """Child process log ingest. Not a user-facing route."""
    if not x_mitm_token or x_mitm_token != _INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid MITM token")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    entry = MitmLog(
        tool=str(body.get("tool") or "unknown"),
        direction=str(body.get("direction") or "request"),
        method=body.get("method"),
        url=body.get("url"),
        status_code=body.get("status_code"),
        latency_ms=body.get("latency_ms"),
        body_preview=body.get("body_preview"),
        headers="{}",
    )
    db.add(entry)
    await db.flush()
    return {"ok": True}


@router.get("/logs", response_model=list[MitmLogOut])
async def get_logs(
    tool: str | None = Query(None, description="Filter by tool name"),
    direction: str | None = Query(
        None,
        description="Filter by direction: request or response",
    ),
    limit: int = Query(50, ge=1, le=500, description="Max logs to return"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Retrieve MITM proxy logs with optional filters."""
    query = select(MitmLog).order_by(MitmLog.timestamp.desc())

    if tool:
        query = query.where(MitmLog.tool == tool)
    if direction:
        query = query.where(MitmLog.direction == direction)

    query = query.limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [MitmLogOut.model_validate(r) for r in rows]


@router.delete("/logs")
async def clear_logs(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Clear all MITM proxy logs."""
    await db.execute(delete(MitmLog))
    return {"status": "cleared", "message": "All MITM logs cleared"}
