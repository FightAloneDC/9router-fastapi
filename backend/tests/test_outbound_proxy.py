"""Unit tests for outbound proxy resolution."""

import asyncio
import json

import pytest

from app.providers.base import BaseProviderConfig, BaseProviderHandler, ValidateResult
from app.routers.providers import testing
from app.services.outbound_proxy import (
    DEFAULT_PROXY_USAGE,
    ProxyRequiredError,
    create_upstream_client,
    merge_proxy_usage_into_data,
    parse_proxy_usage,
    purpose_from_header,
    resolve_proxy_url,
    should_use_proxy,
    use_outbound_proxy,
)


def test_parse_missing_defaults_to_off():
    assert parse_proxy_usage(None)["mode"] == "off"
    assert parse_proxy_usage({}) == DEFAULT_PROXY_USAGE


def test_purpose_header_test_chat():
    assert purpose_from_header("test-chat") == "testChat"
    assert purpose_from_header(None) == "upstream"


def test_selective_test_connection_not_upstream():
    usage = {
        "mode": "selective",
        "flags": {
            "testConnection": True,
            "testModel": False,
            "testChat": False,
            "oauthRefresh": False,
        },
    }
    assert should_use_proxy(usage, "testConnection") is True
    assert should_use_proxy(usage, "upstream") is False


def test_all_uses_proxy_for_upstream():
    usage = {"mode": "all", "flags": dict(DEFAULT_PROXY_USAGE["flags"])}
    assert should_use_proxy(usage, "upstream") is True


class _Pool:
    def __init__(self, url, active=True, strict=False):
        self.proxy_url = url
        self.is_active = active
        self.strict_proxy = strict


def test_resolve_returns_url_when_needed():
    usage = {"mode": "all", "flags": dict(DEFAULT_PROXY_USAGE["flags"])}
    url = resolve_proxy_url(
        usage=usage, purpose="upstream", pool=_Pool("http://p:1")
    )
    assert url == "http://p:1"


def test_resolve_strict_raises_when_inactive():
    usage = {"mode": "all", "flags": dict(DEFAULT_PROXY_USAGE["flags"])}
    with pytest.raises(ProxyRequiredError):
        resolve_proxy_url(
            usage=usage,
            purpose="upstream",
            pool=_Pool("http://p:1", active=False, strict=True),
        )


def test_merge_proxy_usage_into_data():
    data = {"apiKey": "x"}
    usage = {
        "mode": "all",
        "flags": {
            "testConnection": False,
            "testModel": False,
            "testChat": False,
            "oauthRefresh": False,
        },
    }
    out = merge_proxy_usage_into_data(data, usage)
    assert out["apiKey"] == "x"
    assert out["proxyUsage"]["mode"] == "all"


def test_base_validation_inherits_outbound_proxy(monkeypatch):
    """Base validation sends its request through the active proxy context."""
    created = []

    class Response:
        status_code = 200

        def json(self):
            return {"data": []}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    def make_client(**kwargs):
        created.append(kwargs)
        return Client()

    monkeypatch.setattr("httpx.AsyncClient", make_client)
    config = BaseProviderConfig(
        PROVIDER_NAME="Test",
        PROVIDER_ID="test",
        ALIAS="test",
        BASE_URL="https://example.com/v1",
    )
    handler = BaseProviderHandler(config)

    async def run():
        async with use_outbound_proxy("http://proxy.test:8080"):
            return await handler.validate("key")

    assert asyncio.run(run()).valid is True
    assert created == [{"timeout": 15.0, "proxy": "http://proxy.test:8080"}]


def test_connection_test_uses_configured_proxy_pool(monkeypatch):
    """Connection tests resolve proxyUsage before validating credentials."""
    created = []

    class Response:
        status_code = 200

        def json(self):
            return {"data": []}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    def make_client(**kwargs):
        created.append(kwargs)
        return Client()

    class Pool:
        proxy_url = "http://proxy.test:8080"
        is_active = True
        strict_proxy = False

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Db:
        def __init__(self):
            self.results = iter([Result(Pool()), Result(None)])

        async def execute(self, _statement):
            return next(self.results)

    class Handler:
        async def validate(self, _api_key, _data):
            async with create_upstream_client() as client:
                await client.get("https://example.com/v1/models")
            return ValidateResult(valid=True)

    class Provider:
        def __init__(self, _provider):
            pass

        def handler(self):
            return Handler()

    class Connection:
        provider = "test"
        proxy_pool_id = "pool-id"
        data = json.dumps({
            "apiKey": "key",
            "proxyUsage": {"mode": "all", "flags": {}},
        })

    monkeypatch.setattr("httpx.AsyncClient", make_client)
    monkeypatch.setattr(testing, "Provider", Provider)

    result = asyncio.run(testing._test_provider_connection(Connection(), Db()))

    assert result["valid"] is True
    assert created == [{"timeout": 30.0, "proxy": "http://proxy.test:8080"}]


def test_qoder_user_info_inherits_outbound_proxy(monkeypatch):
    """Qoder validation user-info requests inherit the active proxy."""
    from app.providers.qoder.auth import fetch_user_info

    created = []

    class Response:
        status_code = 200

        def json(self):
            return {"id": "user-id"}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    def make_client(**kwargs):
        created.append(kwargs)
        return Client()

    monkeypatch.setattr("httpx.AsyncClient", make_client)

    async def run():
        async with use_outbound_proxy("http://proxy.test:8080"):
            return await fetch_user_info("token")

    assert asyncio.run(run()) == {"id": "user-id"}
    assert created == [{"timeout": 15.0, "proxy": "http://proxy.test:8080"}]


def test_grok_cli_model_fetching_inherits_outbound_proxy(monkeypatch):
    """Grok CLI validation model fetches inherit the active proxy."""
    from app.providers.grok_cli.models import fetch_models

    created = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    def make_client(**kwargs):
        created.append(kwargs)
        return Client()

    monkeypatch.setattr("httpx.AsyncClient", make_client)

    async def run():
        async with use_outbound_proxy("http://proxy.test:8080"):
            return await fetch_models("token")

    assert asyncio.run(run()) == []
    assert created == [{"timeout": 30.0, "proxy": "http://proxy.test:8080"}]
