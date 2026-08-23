"""Settings password change must update users.hashed_password (login source)."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.settings import SettingsModel
from app.models.user import User
from app.routers.settings import update_settings
from app.schemas.settings import SettingsUpdate
from app.services.auth import hash_password, verify_password


async def _run_password_change(
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    settings_row = SettingsModel(id=1, data=json.dumps({}))
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: obj)

    async def _fake_execute(stmt):
        result = MagicMock()
        if "users" in str(stmt).lower():
            result.scalar_one_or_none.return_value = user
        else:
            result.scalar_one_or_none.return_value = settings_row
        return result

    db.execute = _fake_execute

    body = SettingsUpdate(
        currentPassword=current_password,
        newPassword=new_password,
    )
    return await update_settings(body=body, db=db, current_user=user)


def test_update_settings_changes_user_password_not_settings_json():
    old_password = "old-secret"
    new_password = "new-secret"
    user = User(
        id=uuid.uuid4(),
        username="admin",
        hashed_password=hash_password(old_password),
    )

    result = asyncio.run(
        _run_password_change(user, old_password, new_password)
    )

    assert result.hasPassword is True
    assert verify_password(new_password, user.hashed_password)
    assert not verify_password(old_password, user.hashed_password)


def test_update_settings_rejects_wrong_current_password():
    user = User(
        id=uuid.uuid4(),
        username="admin",
        hashed_password=hash_password("correct"),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run_password_change(user, "wrong", "new-secret"))

    assert exc_info.value.status_code == 401
