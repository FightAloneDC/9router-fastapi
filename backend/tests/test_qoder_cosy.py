"""Tests for Qoder qodercli-style signing headers."""

import asyncio

from app.providers.qoder.config import QoderConfig
from app.providers.qoder.constants import (
    QODER_IDE_VERSION,
    QODER_MODEL_LIST_URL,
)
from app.providers.qoder.cosy import build_cosy_headers
from app.providers.qoder.handler import QoderHandler


def test_build_cosy_headers_uses_qodercli_algo_header_shape():
    headers = build_cosy_headers(
        body=b"",
        request_url=QODER_MODEL_LIST_URL,
        user_id="user-1",
        auth_token="jt-token",
        name="Manda Mora",
        email="manda@example.com",
        machine_id="machine-1",
    )

    assert headers["Authorization"].startswith("Bearer COSY.")
    assert headers["Accept"] == "text/event-stream"
    assert headers["Cosy-Version"] == QODER_IDE_VERSION
    assert headers["User-Agent"] == f"Qoder/{QODER_IDE_VERSION}"
    assert QODER_IDE_VERSION == "1.0.48"
    assert headers["Cosy-ClientType"] == "5"
    assert headers["Cosy-Data-Policy"] == "agree"
    assert headers["Cosy-Key"]
    assert headers["Cosy-User"] == "user-1"
    assert headers["Cosy-Date"]
    assert headers["Cosy-MachineId"] == "machine-1"
    assert headers["Cosy-MachineToken"] == "machine-1"
    assert headers["Cosy-MachineType"] == "5"
    assert headers["Cosy-Business-Product"] == "cli"
    assert headers["Cosy-Business-Type"] == "agent"
    assert headers["Cosy-Scene"] == "assistant"
    assert headers["Login-Version"] == "v2"

    assert "Cosy-ClientIp" not in headers
    assert "Accept-Encoding" not in headers
    assert "Cosy-Bodyhash" not in headers
    assert "Cosy-Bodylength" not in headers
    assert "Cosy-Sigpath" not in headers
    assert "Cosy-Machineid" not in headers
    assert "Cosy-Machinetoken" not in headers
    assert "Cosy-Machinetype" not in headers


def test_build_cosy_headers_signature_changes_with_body():
    common = {
        "request_url": QODER_MODEL_LIST_URL,
        "user_id": "user-1",
        "auth_token": "jt-token",
        "machine_id": "machine-1",
        "date": "Tue, 09 Jun 2026 09:20:36 GMT",
    }

    empty_headers = build_cosy_headers(body=b"", **common)
    body_headers = build_cosy_headers(body=b'{"hello":"world"}', **common)

    empty_sig = empty_headers["Authorization"].rsplit(".", 1)[1]
    body_sig = body_headers["Authorization"].rsplit(".", 1)[1]

    assert empty_sig != body_sig


def test_qoder_validate_rejects_inactive_token(monkeypatch):
    async def fake_fetch_user_info(access_token: str):
        raise Exception("Failed to fetch user info: HTTP 401")

    monkeypatch.setattr(
        "app.providers.qoder.auth.fetch_user_info",
        fake_fetch_user_info,
    )

    result = asyncio.run(QoderHandler(QoderConfig()).validate("jt-inactive", {}))

    assert result.valid is False
    assert result.error == "Failed to fetch user info: HTTP 401"


def test_qoder_validate_accepts_active_token(monkeypatch):
    async def fake_fetch_user_info(access_token: str):
        return {"id": "user-1"}

    monkeypatch.setattr(
        "app.providers.qoder.auth.fetch_user_info",
        fake_fetch_user_info,
    )

    result = asyncio.run(QoderHandler(QoderConfig()).validate("dt-active", {}))

    assert result.valid is True
    assert result.error is None


def test_fetch_models_id_is_upstream_key(monkeypatch):
    async def fake_resolve(credentials, force_refresh=False):
        del credentials, force_refresh
        return {
            "models": [
                {"id": "auto", "name": "Auto", "context_length": 128000},
            ],
        }

    monkeypatch.setattr(
        "app.providers.qoder.handler.resolve_qoder_models",
        fake_resolve,
    )
    models = asyncio.run(
        QoderHandler(QoderConfig()).fetch_models(
            "jt-token",
            {"userId": "u1", "machineId": "m1"},
        )
    )
    assert models[0]["id"] == "auto"


def test_build_request_body_rejects_leftover_qoder_prefix(monkeypatch):
    seen: list[str] = []

    def fake_get(user_id, token, key):
        del user_id, token
        seen.append(key)
        return None

    async def fake_resolve(credentials, force_refresh=False):
        del credentials, force_refresh
        return {"models": []}

    monkeypatch.setattr(
        "app.providers.qoder.handler.get_qoder_model_config",
        fake_get,
    )
    monkeypatch.setattr(
        "app.providers.qoder.handler.resolve_qoder_models",
        fake_resolve,
    )
    try:
        asyncio.run(
            QoderHandler(QoderConfig()).build_request_body(
                "qoder/auto",
                {"messages": []},
                {
                    "userId": "u1",
                    "machineId": "m1",
                    "accessToken": "jt",
                },
            )
        )
    except ValueError as exc:
        assert "qoder/auto" in str(exc)
    else:
        raise AssertionError("expected ValueError for leftover prefix")
    assert seen == ["qoder/auto", "qoder/auto"]
