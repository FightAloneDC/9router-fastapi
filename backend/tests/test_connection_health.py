"""Healthy-first connection selection and periodic health refresh."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.services.connection_health import (
    COOLDOWN,
    DEAD,
    EXHAUSTED,
    HEALTHY,
    RATE_LIMITED,
    classify_health,
    health_rank,
    is_connectivity_failure,
    refresh_connection_health,
    resort_connections_by_health,
    resort_rank,
)
from app.services.proxy import select_connection_for_provider


def _conn(
    cid: str,
    priority: int,
    data: dict,
    provider: str = "grok-cli",
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=cid,
        priority=priority,
        provider=provider,
        is_active=is_active,
        data=json.dumps(data),
    )


def test_classify_health_tiers() -> None:
    assert classify_health({})[0] == HEALTHY
    assert classify_health({"errorCode": "429"})[0] == RATE_LIMITED
    assert classify_health({"errorCode": "402"})[0] == EXHAUSTED
    assert classify_health({"errorCode": "401"})[0] == DEAD
    assert classify_health({
        "errorCode": "503",
        "testStatus": "unavailable",
        "lastError": "All connection attempts failed",
    })[0] == COOLDOWN


def test_health_rank_orders_healthy_first() -> None:
    assert health_rank({}) < health_rank({"errorCode": "503"})
    assert health_rank({"errorCode": "503"}) < health_rank(
        {"errorCode": "401"},
    )
    assert health_rank({"errorCode": "429"}) < health_rank(
        {"errorCode": "402"},
    )


def test_fill_first_prefers_healthy_over_higher_priority_dead() -> None:
    dead = _conn("dead", 0, {
        "errorCode": "503",
        "testStatus": "unavailable",
        "lastError": "ConnectError: connection refused",
    })
    healthy = _conn("ok", 9, {"testStatus": "active"})

    picked = select_connection_for_provider(
        [dead, healthy],
        provider_id="grok-cli",
        strategy="fill-first",
    )
    assert picked is not None
    assert str(picked.id) == "ok"


def test_fill_first_keeps_priority_among_healthy() -> None:
    low = _conn("low", 5, {"testStatus": "active"})
    high = _conn("high", 1, {"testStatus": "active"})

    picked = select_connection_for_provider(
        [low, high],
        provider_id="grok-cli",
        strategy="fill-first",
    )
    assert picked is not None
    assert str(picked.id) == "high"


def test_rate_limited_still_skipped() -> None:
    until = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat()
    limited = _conn("lim", 0, {
        "testStatus": "active",
        "rateLimitedUntil": until,
    })
    other = _conn("ok", 9, {"testStatus": "active"})

    picked = select_connection_for_provider(
        [limited, other],
        provider_id="grok-cli",
        strategy="fill-first",
    )
    assert picked is not None
    assert str(picked.id) == "ok"


def test_round_robin_stays_in_healthy_pool() -> None:
    dead = _conn("dead", 0, {
        "errorCode": "503",
        "testStatus": "unavailable",
        "lastError": "connection refused",
    })
    a = _conn("a", 1, {"testStatus": "active"})
    b = _conn("b", 2, {"testStatus": "active"})

    seen: set[str] = set()
    for _ in range(6):
        picked = select_connection_for_provider(
            [dead, a, b],
            provider_id="rr-health",
            strategy="round-robin",
            sticky_limit=1,
        )
        assert picked is not None
        seen.add(str(picked.id))
    assert "dead" not in seen
    assert seen <= {"a", "b"}


def test_all_unhealthy_picks_least_bad_then_priority() -> None:
    dead = _conn("dead", 0, {"errorCode": "401"})
    cool = _conn("cool", 5, {
        "errorCode": "503",
        "testStatus": "unavailable",
    })

    picked = select_connection_for_provider(
        [dead, cool],
        provider_id="grok-cli",
        strategy="fill-first",
    )
    assert picked is not None
    assert str(picked.id) == "cool"


def test_is_connectivity_failure_only_for_reachability() -> None:
    assert is_connectivity_failure({
        "errorCode": "503",
        "lastError": "ConnectTimeout",
    })
    assert is_connectivity_failure({
        "errorCode": "503",
        "lastError": "All connection attempts failed",
    })
    assert not is_connectivity_failure({})
    assert not is_connectivity_failure({"errorCode": "401"})
    assert not is_connectivity_failure({"errorCode": "402"})
    assert not is_connectivity_failure({"errorCode": "429"})


class _ScalarResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list:
        return self._rows


class _Session:
    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.committed = False

    async def execute(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self.rows)

    def add(self, _row: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _SessionCtx:
    def __init__(self, session: _Session) -> None:
        self.session = session

    async def __aenter__(self) -> _Session:
        return self.session

    async def __aexit__(self, *_args: object) -> None:
        return None


def test_refresh_extends_cooldown_when_still_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _conn("dead", 0, {
        "errorCode": "503",
        "testStatus": "unavailable",
        "lastError": "All connection attempts failed",
    })
    session = _Session([conn])

    import app.services.connection_health as health

    monkeypatch.setattr(
        health, "async_session", lambda: _SessionCtx(session),
    )

    async def _down(_db: object, _conn: object, _data: dict) -> bool:
        return False

    monkeypatch.setattr(health, "probe_connection", _down)

    summary = asyncio.run(refresh_connection_health())
    data = json.loads(conn.data)

    assert summary["probed"] == 1
    assert summary["still_down"] == 1
    assert summary["recovered"] == 0
    assert data["testStatus"] == "unavailable"
    until = datetime.fromisoformat(data["rateLimitedUntil"])
    assert until > datetime.now(timezone.utc)
    assert session.committed is True


def test_refresh_recovers_when_host_is_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _conn("back", 0, {
        "errorCode": "503",
        "testStatus": "unavailable",
        "lastError": "connection refused",
        "rateLimitedUntil": (
            datetime.now(timezone.utc) + timedelta(seconds=20)
        ).isoformat(),
        "backoffLevel": 2,
    })
    session = _Session([conn])

    import app.services.connection_health as health

    monkeypatch.setattr(
        health, "async_session", lambda: _SessionCtx(session),
    )

    async def _up(_db: object, _conn: object, _data: dict) -> bool:
        return True

    monkeypatch.setattr(health, "probe_connection", _up)

    summary = asyncio.run(refresh_connection_health())
    data = json.loads(conn.data)

    assert summary["recovered"] == 1
    assert data["testStatus"] == "active"
    assert data.get("errorCode") is None
    assert data.get("lastError") is None
    assert data.get("rateLimitedUntil") is None


def test_refresh_skips_healthy_and_auth_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    healthy = _conn("ok", 0, {"testStatus": "active"})
    exhausted = _conn("ex", 1, {"errorCode": "402"})
    dead = _conn("auth", 2, {"errorCode": "401"})
    session = _Session([healthy, exhausted, dead])

    import app.services.connection_health as health

    monkeypatch.setattr(
        health, "async_session", lambda: _SessionCtx(session),
    )
    probed: list[str] = []

    async def _probe(
        _db: object, conn: object, _data: dict,
    ) -> bool:
        probed.append(str(conn.id))
        return True

    monkeypatch.setattr(health, "probe_connection", _probe)

    summary = asyncio.run(refresh_connection_health())
    assert summary["probed"] == 0
    assert summary["reindexed"] == 0
    assert probed == []
    assert session.committed is False
    assert json.loads(healthy.data)["testStatus"] == "active"
    assert [c.priority for c in (healthy, exhausted, dead)] == [
        0, 1, 2,
    ]


def test_probe_treats_http_response_as_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.connection_health import probe_connection

    import app.services.connection_health as health

    conn = _conn("n", 0, {"baseUrl": "https://example.test"})

    class _Resp:
        status_code = 401

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

        async def get(self, _url: str) -> _Resp:
            return _Resp()

    async def _proxy(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(
        health, "proxy_for_connection", _proxy,
    )
    monkeypatch.setattr(
        health, "create_upstream_client",
        lambda **_k: _Client(),
    )
    monkeypatch.setattr(
        health, "_base_url",
        lambda _p, _d: "https://example.test",
    )

    ok = asyncio.run(probe_connection(None, conn, {"baseUrl": "x"}))
    assert ok is True


def test_probe_treats_connect_error_as_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.connection_health import probe_connection

    import app.services.connection_health as health

    conn = _conn("n", 0, {})

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

        async def get(self, _url: str) -> object:
            raise httpx.ConnectError("connection refused")

    async def _proxy(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(
        health, "proxy_for_connection", _proxy,
    )
    monkeypatch.setattr(
        health, "create_upstream_client",
        lambda **_k: _Client(),
    )
    monkeypatch.setattr(
        health, "_base_url",
        lambda _p, _d: "https://dead.test",
    )

    ok = asyncio.run(probe_connection(None, conn, {}))
    assert ok is False


def test_resort_moves_healthy_to_index_zero() -> None:
    dead = _conn("dead", 0, {"errorCode": "401"})
    exhausted = _conn("ex", 1, {"errorCode": "402"})
    limited = _conn("lim", 2, {"errorCode": "429"})
    healthy = _conn("ok", 9, {"testStatus": "active"})

    moved = resort_connections_by_health(
        [dead, exhausted, limited, healthy],
    )

    assert healthy.priority == 0
    assert limited.priority == 1
    assert exhausted.priority == 2
    assert dead.priority == 3
    ids = {str(conn.id) for conn, _old, _new in moved}
    assert "ok" in ids
    assert "dead" in ids


def test_resort_keeps_order_among_healthy() -> None:
    high = _conn("high", 1, {"testStatus": "active"})
    low = _conn("low", 5, {"testStatus": "active"})
    dead = _conn("dead", 0, {"errorCode": "401"})

    moved = resort_connections_by_health([low, high, dead])

    assert high.priority == 0
    assert low.priority == 1
    assert dead.priority == 2
    assert {str(c.id) for c, _o, _n in moved} == {
        "high", "low", "dead",
    }


def test_resort_pushes_active_cooldown_behind_healthy() -> None:
    until = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat()
    cooling = _conn("cool", 0, {
        "testStatus": "active",
        "rateLimitedUntil": until,
    })
    healthy = _conn("ok", 1, {"testStatus": "active"})

    assert resort_rank(json.loads(cooling.data)) == 1
    resort_connections_by_health([cooling, healthy])
    assert healthy.priority == 0
    assert cooling.priority == 1


def test_resort_places_inactive_last() -> None:
    inactive_ok = _conn(
        "off", 0, {"testStatus": "active"}, is_active=False,
    )
    dead = _conn("dead", 1, {"errorCode": "401"})
    healthy = _conn("ok", 2, {"testStatus": "active"})

    resort_connections_by_health([inactive_ok, dead, healthy])
    assert healthy.priority == 0
    assert dead.priority == 1
    assert inactive_ok.priority == 2


def test_refresh_resorts_when_nothing_probed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dead = _conn("dead", 0, {"errorCode": "401"})
    healthy = _conn("ok", 4, {"testStatus": "active"})
    session = _Session([dead, healthy])

    import app.services.connection_health as health

    monkeypatch.setattr(
        health, "async_session", lambda: _SessionCtx(session),
    )

    async def _probe(*_a: object, **_k: object) -> bool:
        raise AssertionError("must not probe auth/healthy")

    monkeypatch.setattr(health, "probe_connection", _probe)

    summary = asyncio.run(refresh_connection_health())
    assert summary["probed"] == 0
    assert summary["resorted"] == 1
    assert summary["reindexed"] == 2
    assert healthy.priority == 0
    assert dead.priority == 1
    assert session.committed is True


def test_refresh_resorts_each_provider_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    g_dead = _conn("g-dead", 0, {"errorCode": "402"})
    g_ok = _conn("g-ok", 3, {"testStatus": "active"})
    q_ok = _conn(
        "q-ok", 0, {"testStatus": "active"}, provider="qoder",
    )
    q_dead = _conn(
        "q-dead", 1, {"errorCode": "401"}, provider="qoder",
    )
    session = _Session([g_dead, g_ok, q_ok, q_dead])

    import app.services.connection_health as health

    monkeypatch.setattr(
        health, "async_session", lambda: _SessionCtx(session),
    )

    async def _probe(*_a: object, **_k: object) -> bool:
        return False

    monkeypatch.setattr(health, "probe_connection", _probe)

    summary = asyncio.run(refresh_connection_health())
    assert summary["resorted"] == 1
    assert g_ok.priority == 0
    assert g_dead.priority == 1
    assert q_ok.priority == 0
    assert q_dead.priority == 1


def test_refresh_recovers_then_promotes_to_index_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    down = _conn("was-down", 0, {
        "errorCode": "503",
        "testStatus": "unavailable",
        "lastError": "connection refused",
    })
    healthy = _conn("ok", 1, {"testStatus": "active"})
    session = _Session([down, healthy])

    import app.services.connection_health as health

    monkeypatch.setattr(
        health, "async_session", lambda: _SessionCtx(session),
    )

    async def _up(_db: object, _conn: object, _data: dict) -> bool:
        return True

    monkeypatch.setattr(health, "probe_connection", _up)

    summary = asyncio.run(refresh_connection_health())
    assert summary["recovered"] == 1
    data = json.loads(down.data)
    assert data.get("errorCode") is None
    assert down.priority == 0
    assert healthy.priority == 1


class _MarkSession:
    """Session mock for mark_connection_unavailable + resort."""

    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.committed = False

    async def execute(self, _statement: object) -> "_MarkResult":
        return _MarkResult(self.rows)

    def add(self, _row: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _MarkResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None

    def scalars(self) -> "_MarkResult":
        return self

    def all(self) -> list:
        return self._rows


def test_mark_unavailable_reindexes_exhausted_behind_healthy() -> None:
    from app.services.proxy import mark_connection_unavailable

    exhausted = _conn("ex", 0, {"testStatus": "active"})
    healthy = _conn("ok", 1, {"testStatus": "active"})
    session = _MarkSession([exhausted, healthy])

    asyncio.run(mark_connection_unavailable(
        session,  # type: ignore[arg-type]
        "ex",
        cooldown_ms=5_000,
        status_code=402,
        error_detail="spending limit",
    ))

    assert session.committed is True
    blob = json.loads(exhausted.data)
    assert blob["errorCode"] == "402"
    assert healthy.priority == 0
    assert exhausted.priority == 1
