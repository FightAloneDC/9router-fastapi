"""Unit tests for connection proxy usage request and response fields."""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.routers.providers.helpers import (
    _connection_to_out,
    _sanitize_connection,
)
from app.schemas.provider import (
    ProviderConnectionCreate,
    ProviderConnectionOut,
    ProviderConnectionUpdate,
)


PROXY_USAGE = {
    "mode": "selective",
    "flags": {
        "testConnection": True,
        "testModel": False,
        "testChat": True,
        "oauthRefresh": False,
    },
}


def test_connection_schemas_accept_proxy_usage():
    created = ProviderConnectionCreate(
        provider="test",
        proxyUsage=PROXY_USAGE,
    )
    updated = ProviderConnectionUpdate(proxyUsage=PROXY_USAGE)

    assert created.proxyUsage == PROXY_USAGE
    assert updated.proxyUsage == PROXY_USAGE


def test_connection_serialization_exposes_proxy_usage():
    connection = SimpleNamespace(
        id=uuid.uuid4(),
        provider="test",
        auth_type="apikey",
        name="Test",
        email=None,
        priority=0,
        is_active=True,
        proxy_pool_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
        data=json.dumps({"proxyUsage": PROXY_USAGE}),
    )

    serialized = _connection_to_out(connection)
    client = _sanitize_connection(serialized)
    response = ProviderConnectionOut.model_validate(serialized)

    assert serialized["proxyUsage"] == PROXY_USAGE
    assert client["proxyUsage"] == PROXY_USAGE
    assert response.proxyUsage == PROXY_USAGE
