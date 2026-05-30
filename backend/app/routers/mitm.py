"""MITM proxy management endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mitm import MitmConfig, MitmLog
from app.routers.auth import get_current_user
from app.schemas.mitm import MitmConfigOut, MitmConfigUpdate, MitmLogOut

router = APIRouter(prefix="/mitm", tags=["mitm"])

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

    await db.flush()
    await db.refresh(row)
    return MitmConfigOut.model_validate(row)


@router.post("/start")
async def start_mitm(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Start the MITM proxy server (placeholder)."""
    row = await _get_or_create_config(db)
    row.enabled = True
    await db.flush()
    return {"status": "started", "message": "MITM proxy start initiated"}


@router.post("/stop")
async def stop_mitm(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Stop the MITM proxy server (placeholder)."""
    row = await _get_or_create_config(db)
    row.enabled = False
    await db.flush()
    return {"status": "stopped", "message": "MITM proxy stop initiated"}


@router.post("/generate-cert")
async def generate_cert(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Generate SSL certificate for MITM proxy (placeholder)."""
    row = await _get_or_create_config(db)
    row.cert_generated = True
    await db.flush()
    return {"status": "generated", "message": "SSL certificate generated successfully"}


@router.get("/status")
async def get_status(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get MITM proxy server status."""
    row = await _get_or_create_config(db)

    # Parse tools config to derive DNS status per tool
    try:
        tools = json.loads(row.tools_config)
    except json.JSONDecodeError:
        tools = {}

    dns_status = {
        tool: cfg.get("dnsEnabled", False) for tool, cfg in tools.items()
    }

    return {
        "running": row.enabled,
        "certExists": row.cert_generated,
        "dnsStatus": dns_status,
    }


@router.get("/logs", response_model=list[MitmLogOut])
async def get_logs(
    tool: str | None = Query(None, description="Filter by tool name"),
    direction: str | None = Query(None, description="Filter by direction: request or response"),
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
