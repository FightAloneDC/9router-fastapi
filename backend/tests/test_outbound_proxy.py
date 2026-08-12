"""Unit tests for outbound proxy resolution."""

import pytest

from app.services.outbound_proxy import (
    DEFAULT_PROXY_USAGE,
    ProxyRequiredError,
    merge_proxy_usage_into_data,
    parse_proxy_usage,
    purpose_from_header,
    resolve_proxy_url,
    should_use_proxy,
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
