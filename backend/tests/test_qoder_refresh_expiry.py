"""Qoder refresh must persist expiresAt (ms/seconds aware)."""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.providers.qoder.auth import (
    apply_qoder_token_expiry,
    expires_in_to_seconds,
    mark_refresh_rejected,
    refresh_all_qoder_connections,
    refresh_token_unusable,
    try_refresh_connection,
)


def test_expires_in_ms_vs_seconds() -> None:
    assert expires_in_to_seconds(86400000) == 86400
    assert expires_in_to_seconds(3600) == 3600
    assert expires_in_to_seconds(None) is None
    assert expires_in_to_seconds("bad") is None


def test_apply_qoder_token_expiry_from_ms() -> None:
    data: dict = {}
    now = datetime(2026, 8, 12, 21, 0, 0, tzinfo=timezone.utc)
    apply_qoder_token_expiry(
        data,
        {
            "expires_in": 86400000,
            "refresh_token_expires_in": 172800000,
        },
        now=now,
    )
    assert data["expiresAt"].startswith("2026-08-13T21:00:00")
    assert data["refreshTokenExpiresAt"].startswith(
        "2026-08-14T21:00:00",
    )


def test_apply_qoder_token_expiry_prefers_absolute() -> None:
    data: dict = {}
    apply_qoder_token_expiry(
        data,
        {
            "expires_at": "2026-08-13T12:00:00Z",
            "refresh_token_expires_at": "2026-08-14T12:00:00Z",
            "expires_in": 1,
        },
    )
    assert data["expiresAt"] == "2026-08-13T12:00:00Z"
    assert data["refreshTokenExpiresAt"] == "2026-08-14T12:00:00Z"


class _Scalar:
    def __init__(self, row: object) -> None:
        self._row = row

    def scalar_one_or_none(self) -> object:
        return self._row


class _Db:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def execute(self, _statement: object) -> _Scalar:
        return _Scalar(self.conn)

    async def flush(self) -> None:
        return None


def _refresh_conn(refresh_token: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="conn-1",
        provider="qoder",
        data=json.dumps({
            "accessToken": "dt-old",
            "refreshToken": refresh_token,
        }),
    )


def test_try_refresh_sends_oauth_drt_to_job_token(
    monkeypatch,
) -> None:
    import app.providers.qoder.auth as auth

    seen: list[str] = []

    async def _refresh(
        token: str, timeout: float = 15.0,
    ) -> tuple[dict, int]:
        seen.append(token)
        return {
            "access_token": "dt-new",
            "refresh_token": "drt-new",
            "expires_in": 3600,
        }, 200

    async def _proxy(*_a: object, **_k: object) -> None:
        return None

    class _ProxyCtx:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(auth, "refresh_job_token_result", _refresh)
    monkeypatch.setattr(auth, "proxy_for_connection", _proxy)
    monkeypatch.setattr(
        auth, "use_outbound_proxy", lambda _p: _ProxyCtx(),
    )
    monkeypatch.setattr(
        "app.services.proxy.invalidate_connection_cache",
        lambda *_a, **_k: None,
    )

    conn = _refresh_conn("drt-oauth")
    ok = asyncio.run(try_refresh_connection(_Db(conn), "conn-1"))
    assert ok is True
    assert seen == ["drt-oauth"]
    blob = json.loads(conn.data)
    assert blob["refreshToken"] == "drt-new"
    assert blob["accessToken"] == "dt-new"


def test_try_refresh_sends_pat_jrt_to_job_token(
    monkeypatch,
) -> None:
    import app.providers.qoder.auth as auth

    seen: list[str] = []

    async def _refresh(
        token: str, timeout: float = 15.0,
    ) -> tuple[dict, int]:
        seen.append(token)
        return {
            "access_token": "jt-new",
            "refresh_token": "jrt-new",
            "expires_in": 3600,
        }, 200

    async def _proxy(*_a: object, **_k: object) -> None:
        return None

    class _ProxyCtx:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(auth, "refresh_job_token_result", _refresh)
    monkeypatch.setattr(auth, "proxy_for_connection", _proxy)
    monkeypatch.setattr(
        auth, "use_outbound_proxy", lambda _p: _ProxyCtx(),
    )
    monkeypatch.setattr(
        "app.services.proxy.invalidate_connection_cache",
        lambda *_a, **_k: None,
    )

    conn = _refresh_conn("jrt-pat")
    ok = asyncio.run(try_refresh_connection(_Db(conn), "conn-1"))
    assert ok is True
    assert seen == ["jrt-pat"]
    blob = json.loads(conn.data)
    assert blob["refreshToken"] == "jrt-new"


def test_refresh_token_unusable_only_for_same_token() -> None:
    data = {"refreshToken": "drt-old"}
    assert refresh_token_unusable(data) is False
    mark_refresh_rejected(data, 400)
    assert data["invalidRefreshToken"] == "drt-old"
    assert refresh_token_unusable(data) is True
    data["refreshToken"] = "drt-fresh"
    assert refresh_token_unusable(data) is False


def test_try_refresh_skips_already_rejected_token(
    monkeypatch,
) -> None:
    import app.providers.qoder.auth as auth

    called = False

    async def _refresh(*_a: object, **_k: object) -> tuple:
        nonlocal called
        called = True
        return None, 400

    monkeypatch.setattr(auth, "refresh_job_token_result", _refresh)
    conn = _refresh_conn("drt-dead")
    blob = json.loads(conn.data)
    blob["invalidRefreshToken"] = "drt-dead"
    conn.data = json.dumps(blob)

    ok = asyncio.run(try_refresh_connection(_Db(conn), "conn-1"))
    assert ok is False
    assert called is False


def test_try_refresh_reexchanges_stored_pat_when_refresh_dead(
    monkeypatch,
) -> None:
    import app.providers.qoder.auth as auth

    refresh_called = False

    async def _refresh(*_a: object, **_k: object) -> tuple:
        nonlocal refresh_called
        refresh_called = True
        return None, 400

    async def _exchange(pat: str, timeout: float = 30.0) -> dict:
        assert pat == "pt-keep"
        return {
            "access_token": "jt-from-pat",
            "refresh_token": "jrt-from-pat",
            "expires_in": 3600,
        }

    async def _proxy(*_a: object, **_k: object) -> None:
        return None

    class _ProxyCtx:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(auth, "refresh_job_token_result", _refresh)
    monkeypatch.setattr(auth, "exchange_personal_token", _exchange)
    monkeypatch.setattr(auth, "proxy_for_connection", _proxy)
    monkeypatch.setattr(
        auth, "use_outbound_proxy", lambda _p: _ProxyCtx(),
    )
    monkeypatch.setattr(
        "app.services.proxy.invalidate_connection_cache",
        lambda *_a, **_k: None,
    )

    conn = _refresh_conn("jrt-dead")
    blob = json.loads(conn.data)
    blob["invalidRefreshToken"] = "jrt-dead"
    blob["personalToken"] = "pt-keep"
    conn.data = json.dumps(blob)

    ok = asyncio.run(try_refresh_connection(_Db(conn), "conn-1"))
    assert ok is True
    assert refresh_called is False
    out = json.loads(conn.data)
    assert out["accessToken"] == "jt-from-pat"
    assert out["refreshToken"] == "jrt-from-pat"
    assert out["personalToken"] == "pt-keep"


def test_background_marks_400_then_skips(
    monkeypatch,
) -> None:
    import app.providers.qoder.auth as auth

    dead = _refresh_conn("drt-dead")
    dead.id = "aaaaaaaa-1111-2222-3333-444444444444"
    hits: list[str] = []

    class _Result:
        def scalars(self) -> "_Result":
            return self

        def all(self) -> list:
            return [dead]

    class _Session:
        async def execute(self, _s: object) -> _Result:
            return _Result()

        def add(self, _c: object) -> None:
            return None

        async def commit(self) -> None:
            return None

    class _Ctx:
        async def __aenter__(self) -> _Session:
            return _Session()

        async def __aexit__(self, *_a: object) -> None:
            return None

    async def _refresh(token: str, timeout: float = 15.0) -> tuple:
        hits.append(token)
        return None, 400

    async def _proxy(*_a: object, **_k: object) -> None:
        return None

    class _ProxyCtx:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(
        "app.database.async_sessionmaker",
        lambda *_a, **_k: lambda: _Ctx(),
    )
    monkeypatch.setattr(auth, "refresh_job_token_result", _refresh)
    monkeypatch.setattr(auth, "proxy_for_connection", _proxy)
    monkeypatch.setattr(
        auth, "use_outbound_proxy", lambda _p: _ProxyCtx(),
    )
    monkeypatch.setattr(
        "app.services.proxy.invalidate_connection_cache",
        lambda *_a, **_k: None,
    )

    first = asyncio.run(refresh_all_qoder_connections())
    assert first == {str(dead.id): False}
    assert hits == ["drt-dead"]
    blob = json.loads(dead.data)
    assert blob["invalidRefreshToken"] == "drt-dead"
    assert blob["errorCode"] == "400"

    second = asyncio.run(refresh_all_qoder_connections())
    assert second == {}
    assert hits == ["drt-dead"]
