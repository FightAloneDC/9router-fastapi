"""CLI tools configuration endpoints."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cli_tool import CliToolConfig
from app.routers.auth import get_current_user
from app.schemas.cli_tool import CliToolConfigOut, CliToolConfigUpdate

router = APIRouter(prefix="/cli-tools", tags=["cli-tools"])


@router.get("", response_model=list[CliToolConfigOut])
async def list_cli_tools(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return all CLI tool configurations."""
    result = await db.execute(select(CliToolConfig))
    rows = result.scalars().all()
    return [CliToolConfigOut.model_validate(row) for row in rows]


@router.get("/{tool_id}", response_model=CliToolConfigOut)
async def get_cli_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return a single CLI tool configuration."""
    result = await db.execute(
        select(CliToolConfig).where(CliToolConfig.id == tool_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CLI tool '{tool_id}' not found",
        )
    return CliToolConfigOut.model_validate(row)


@router.patch("/{tool_id}", response_model=CliToolConfigOut)
async def update_cli_tool(
    tool_id: str,
    body: CliToolConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Update a CLI tool configuration (partial merge)."""
    result = await db.execute(
        select(CliToolConfig).where(CliToolConfig.id == tool_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        # Auto-create the row on first update
        row = CliToolConfig(id=tool_id, enabled=False, config_data="{}")
        db.add(row)
        await db.flush()

    update_data = body.model_dump(exclude_unset=True)

    if "enabled" in update_data:
        row.enabled = update_data["enabled"]

    if "config_data" in update_data:
        # Merge with existing config_data
        try:
            current = json.loads(row.config_data) if row.config_data else {}
        except (json.JSONDecodeError, TypeError):
            current = {}
        incoming = update_data["config_data"]
        if isinstance(incoming, str):
            try:
                incoming = json.loads(incoming)
            except (json.JSONDecodeError, TypeError):
                incoming = {}
        if isinstance(incoming, dict) and isinstance(current, dict):
            current.update(incoming)
        else:
            current = incoming
        row.config_data = json.dumps(current)

    row.last_configured_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(row)

    return CliToolConfigOut.model_validate(row)
