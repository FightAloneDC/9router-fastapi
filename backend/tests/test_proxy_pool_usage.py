"""Unit tests for applying proxy pool usage templates."""

import json
from types import SimpleNamespace

import pytest

from app.routers.proxy_pools import apply_pool_usage_to_connections


class _Result:
    def __init__(self, connections):
        self._connections = connections

    def scalars(self):
        return self

    def all(self):
        return self._connections


class _Database:
    async def execute(self, _statement):
        return _Result(self.connections)


@pytest.mark.anyio
async def test_apply_pool_usage_merges_template_into_connections():
    pool = SimpleNamespace(
        id="pool-id",
        default_proxy_usage={
            "mode": "all",
            "flags": {
                "testConnection": False,
                "testModel": False,
                "testChat": False,
                "oauthRefresh": False,
            },
        },
    )
    connection = SimpleNamespace(data=json.dumps({"apiKey": "secret"}))
    db = _Database()
    db.connections = [connection]

    updated = await apply_pool_usage_to_connections(db, pool)

    assert updated == 1
    assert json.loads(connection.data) == {
        "apiKey": "secret",
        "proxyUsage": {
            "mode": "all",
            "flags": {
                "testConnection": False,
                "testModel": False,
                "testChat": False,
                "oauthRefresh": False,
            },
        },
    }
