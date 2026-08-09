#!/usr/bin/env python3
"""Scratch: verify refresh auto-disable on invalid_grant.

Creates a throwaway grok-cli connection with a dead refresh token
(passed via TEST_RT env var) and an expired expiresAt, runs one
token-refresh cycle, verifies the connection got auto-disabled,
then deletes it.

Usage (inside backend container):
    TEST_RT=<dead refresh token> uv run python tests/_scratch_auto_disable.py
"""

import json
import os
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session
from app.models.provider import ProviderConnection
from app.services.token_refresh import check_and_refresh_tokens

EMAIL = "auto-disable-test@example.com"


async def main() -> int:
    refresh_token = os.environ.get("TEST_RT", "")
    if not refresh_token:
        print("ERROR: TEST_RT env var not set")
        return 1

    expires = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    data = {
        "accessToken": "stale-access-token",
        "refreshToken": refresh_token,
        "expiresAt": expires,
        "testStatus": "active",
    }
    async with async_session() as session:
        conn = ProviderConnection(
            provider="grok-cli", auth_type="oauth",
            name=EMAIL, email=EMAIL, data=json.dumps(data),
        )
        session.add(conn)
        await session.commit()
        await session.refresh(conn)
        conn_id = conn.id
        print("created test connection:", conn_id)

    summary = await check_and_refresh_tokens()
    print("cycle: refreshed=%s failed=%s skipped=%s" % (
        summary["refreshed"], summary["failed"], summary["skipped"],
    ))

    ok = False
    async with async_session() as session:
        conn = (await session.execute(
            select(ProviderConnection).where(
                ProviderConnection.id == conn_id,
            )
        )).scalar_one()
        blob = json.loads(conn.data)
        print("is_active:", conn.is_active)
        print("errorCode:", blob.get("errorCode"))
        print("lastError:", str(blob.get("lastError"))[:120])
        ok = conn.is_active is False
        await session.delete(conn)
        await session.commit()

    print("cleanup: test connection deleted")
    print("AUTO-DISABLE OK" if ok else "AUTO-DISABLE FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
