"""API key authentication for /v1/ proxy routes.

Accepts both API keys (from api_keys table) and JWT tokens.
Priority: API key first, then JWT fallback.
Returns None if auth not required (requireApiKey=False).
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.api_key import ApiKey
from app.models.settings import SettingsModel

import json


async def _require_api_key_setting(db: AsyncSession) -> bool:
    """Check if API key requirement is enabled in settings."""
    result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    row = result.scalar_one_or_none()
    if row and row.data:
        data = json.loads(row.data)
        return data.get("requireApiKey", False)
    return False


async def validate_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Validate Bearer token for /v1/ routes.

    Accepts both API keys (from api_keys table) and JWT tokens.
    Priority: API key first, then JWT fallback.
    Returns None if auth not required (requireApiKey=False).
    """
    require_key = await _require_api_key_setting(db)

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        if not require_key:
            return None  # No auth required, no token provided
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]  # Remove "Bearer " prefix

    # Try API key first
    result = await db.execute(
        select(ApiKey).where(ApiKey.key == token, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if api_key:
        return {"id": api_key.id, "name": api_key.name, "auth_type": "api_key"}

    # Fallback: try JWT
    from app.services.auth import decode_access_token, get_user_by_username

    payload = decode_access_token(token)
    if payload and payload.get("sub"):
        user = await get_user_by_username(db, payload["sub"])
        if user:
            return {"id": user.id, "name": user.username, "auth_type": "jwt"}

    if not require_key:
        return None  # Auth not required, token was invalid but we don't care

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or inactive API key / JWT token",
        headers={"WWW-Authenticate": "Bearer"},
    )
