"""Phantom-write anomaly detection and routing skip."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.providers.grok_cli.anomaly import (
    RETRY_USER_TEXT,
    evaluate_phantom_write,
    history_has_mutating_write,
    inject_retry_upstream,
    is_phantom_write,
    request_has_write_tools,
    user_has_write_intent,
)
from app.services.connection_health import (
    HEALTHY,
    classify_health,
    is_connectivity_failure,
)
from app.services.proxy import (
    is_anomalous,
    select_connection_for_provider,
    should_fallback_on_error,
)

USER_WRITE = (
    "pelajari keseluruhan projek ini , lalu audit cari "
    "potensi bug memory atau race condition, hasil audit "
    "tulis ke file dokumen"
)

V1_CONTENT = (
    "**Audit lengkap telah selesai.**\n\n"
    "Saya sudah menulis ulang ke "
    "`docs/AUDIT_MEMORY_RACE_2026-08-14.md` "
    "(full 18 halaman, termasuk severity)."
)

V3_CONTENT = (
    "**File dokumen audit sudah saya simpan sebagai:**\n"
    "`/mnt/E07854D07854A6D6/Project/Project-Xubuntu/"
    "ssh-roundrobin/AUDIT_MEMORY_RACE_2026-08-14.md`\n\n"
    "Saya akan buat file tersebut sekarang dengan detail "
    "lengkap + rekomendasi perbaikan + poin prioritas."
)

WRITE_TOOLS = [
    {
        "type": "function",
        "function": {"name": "Write", "parameters": {}},
    },
    {
        "type": "function",
        "function": {"name": "Read", "parameters": {}},
    },
]

DUMP_ROOT = (
    Path(__file__).resolve().parents[2] / ".scratch" / "grok-cli"
)


def _req(content: str, tools: list | None = None) -> dict:
    return {
        "tools": tools if tools is not None else WRITE_TOOLS,
        "messages": [
            {"role": "user", "content": USER_WRITE},
            {"role": "assistant", "content": "ok"},
        ],
    }


def _stop(content: str, tool_calls: list | None = None) -> dict:
    return {
        "content": content,
        "tool_calls": tool_calls or [],
        "finish_reason": "stop",
    }


def _conn(cid: str, priority: int, data: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=cid,
        priority=priority,
        provider="grok-cli",
        is_active=True,
        data=json.dumps(data),
    )


def test_request_has_write_tools() -> None:
    assert request_has_write_tools({"tools": WRITE_TOOLS}) is True
    assert request_has_write_tools({
        "tools": [{"name": "Read"}],
    }) is False
    assert request_has_write_tools({"tools": []}) is False


def test_user_has_write_intent() -> None:
    assert user_has_write_intent(_req(USER_WRITE)) is True
    assert user_has_write_intent({
        "messages": [{"role": "user", "content": "apa kabar?"}],
    }) is False
    assert user_has_write_intent({
        "messages": [{"role": "user", "content": (
            "Setelah audit, WAJIB simpan hasilnya ke file "
            "(bukan hanya di chat):\n"
            "docs/AUDIT.md\n"
            "- Tulis file itu dengan tool Write"
        )}],
    }) is True
    assert user_has_write_intent({
        "messages": [{"role": "user", "content": (
            "coba tulis file grok-test.txt isinya `grok was here`"
        )}],
    }) is True
    assert user_has_write_intent({
        "messages": [{"role": "user", "content": (
            "Pelajari proyek ini, lalu audit potensi memory leak, "
            "resource leak, dan race condition. Hasil audit simpan "
            "ke docs/AUDIT_MEMORY_RACE_2026-08-14.md"
        )}],
    }) is True


def test_formula_hits_v1_and_v3_phrasing() -> None:
    assert is_phantom_write(_req(USER_WRITE), _stop(V1_CONTENT))
    assert is_phantom_write(_req(USER_WRITE), _stop(V3_CONTENT))


def test_formula_misses_investigation_tool_calls() -> None:
    assert is_phantom_write(_req(USER_WRITE), {
        "content": "Saya akan pelajari struktur proyek dulu.",
        "tool_calls": [{
            "function": {"name": "Read", "arguments": "{}"},
        }],
        "finish_reason": "tool_calls",
    }) is False


def test_formula_misses_real_write_tool() -> None:
    assert is_phantom_write(_req(USER_WRITE), {
        "content": "",
        "tool_calls": [{
            "function": {
                "name": "Write",
                "arguments": '{"path":"AUDIT.md"}',
            },
        }],
        "finish_reason": "tool_calls",
    }) is False


def test_formula_misses_without_write_tools() -> None:
    req = {
        "tools": [{"function": {"name": "Read"}}],
        "messages": [{"role": "user", "content": USER_WRITE}],
    }
    assert is_phantom_write(req, _stop(V3_CONTENT)) is False


def test_formula_misses_without_user_intent() -> None:
    req = {
        "tools": WRITE_TOOLS,
        "messages": [{"role": "user", "content": "jelaskan kode ini"}],
    }
    assert is_phantom_write(req, _stop(V3_CONTENT)) is False


def test_formula_misses_empty_stop() -> None:
    assert is_phantom_write(_req(USER_WRITE), _stop("")) is False


def test_formula_still_hits_after_bash_only_history() -> None:
    req = {
        "tools": WRITE_TOOLS,
        "messages": [
            {"role": "user", "content": USER_WRITE},
            {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "Bash",
                        "arguments": '{"command":"go test -race ./..."}',
                    },
                }],
            },
            {"role": "tool", "content": "ok"},
        ],
    }
    assert history_has_mutating_write(req) is False
    assert is_phantom_write(req, _stop(
        "File audit disimpan ke docs/AUDIT_BUG_2026-08-14.md",
    )) is True


def test_formula_misses_after_successful_write() -> None:
    req = {
        "tools": WRITE_TOOLS,
        "messages": [
            {"role": "user", "content": USER_WRITE},
            {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "Write",
                        "arguments": '{"path":"grok-test.txt"}',
                    },
                }],
            },
            {"role": "tool", "content": "ok"},
            {"role": "user", "content": USER_WRITE},
        ],
    }
    assert history_has_mutating_write(req) is True
    assert is_phantom_write(req, _stop(
        "grok-test.txt berhasil ditulis",
    )) is False


def test_exhausted_429_should_fallback() -> None:
    err = (
        "You've used all the included free usage for model "
        "grok-4.6"
    )
    assert should_fallback_on_error(429, err) is True
    assert should_fallback_on_error(400, "bad request") is False


def test_inject_retry_upstream_appends_nudge() -> None:
    out = inject_retry_upstream(
        {"model": "grok-4.6", "input": [{"role": "user"}]},
        {"content": "saved to docs/AUDIT.md"},
    )
    assert out["stream"] is True
    assert out["tool_choice"] == "required"
    text = out["input"][-1]["content"][0]["text"]
    assert RETRY_USER_TEXT in text
    assert "saved to docs/AUDIT.md" in text
    assert out["input"][-1]["role"] == "user"
    assert out["input"][-1]["content"][0]["type"] == "input_text"


def test_anomaly_blob_stays_refreshable() -> None:
    data = {
        "anomaly": True,
        "anomalyReason": "Phantom write",
        "testStatus": "active",
        "accessToken": "tok",
        "refreshToken": "ref",
    }
    assert is_anomalous(data) is True
    assert classify_health(data)[0] == HEALTHY
    assert is_connectivity_failure(data) is False


def test_select_skips_anomalous_connection() -> None:
    bad = _conn("bad", 0, {
        "testStatus": "active",
        "anomaly": True,
    })
    ok = _conn("ok", 9, {"testStatus": "active"})
    picked = select_connection_for_provider(
        [bad, ok],
        provider_id="grok-cli",
        strategy="fill-first",
    )
    assert picked is not None
    assert str(picked.id) == "ok"


def test_select_returns_none_if_only_anomalous() -> None:
    bad = _conn("bad", 0, {"anomaly": True})
    picked = select_connection_for_provider(
        [bad],
        provider_id="grok-cli",
        strategy="fill-first",
    )
    assert picked is None


def test_token_refresh_pops_do_not_clear_anomaly() -> None:
    data = {
        "anomaly": True,
        "anomalyReason": "Phantom write",
        "anomalyAt": datetime.now(timezone.utc).isoformat(),
        "lastError": "Phantom write",
        "lastErrorAt": datetime.now(timezone.utc).isoformat(),
        "errorCode": None,
        "rateLimitedUntil": (
            datetime.now(timezone.utc) + timedelta(minutes=1)
        ).isoformat(),
    }
    data.pop("lastError", None)
    data.pop("lastErrorAt", None)
    data.pop("errorCode", None)
    assert data["anomaly"] is True
    assert data["anomalyReason"] == "Phantom write"
    assert is_anomalous(data) is True


@pytest.mark.skipif(
    not DUMP_ROOT.exists(),
    reason="no local grok-cli dumps",
)
def test_live_dumps_match_formula() -> None:
    """All local dump pairs: stop+write-task hit, tool_calls miss."""
    pairs = list(DUMP_ROOT.glob("*_response.json"))
    pairs += list((DUMP_ROOT / "v1").glob("*_response.json"))
    assert pairs, "expected dump pairs"
    for response_path in pairs:
        client_path = Path(
            str(response_path).replace(
                "_response.json", "_client.json",
            )
        )
        response = json.loads(response_path.read_text())
        client = json.loads(client_path.read_text())
        signals = evaluate_phantom_write(
            client["client_request"],
            response["response"],
        )
        finish = response["meta"]["finish_reason"]
        names = response["meta"].get("tool_call_names") or []
        wrote = any(
            n.lower() in ("write", "edit", "bash")
            for n in names
        )
        if finish == "tool_calls" or wrote:
            assert signals["hit"] is False, response_path.name
            continue
        if finish == "stop" and signals["fresh"]:
            # Write-intent stops without a prior Write should retry.
            if signals["write_tools"] and signals["user_intent"]:
                assert signals["hit"] is True, response_path.name
