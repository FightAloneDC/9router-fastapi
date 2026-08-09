#!/usr/bin/env python3
"""Scratch: verify grok-cli bulk-import endpoint with dummy data.

Creates one throwaway connection, exercises create/skip/upsert/expired
paths, then deletes the connection again.
"""

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "http://localhost:8013"
PROVIDER = sys.argv[1] if len(sys.argv) > 1 else "grok-cli"
EMAIL = "bulk-test-1@example.com"


def _req(method: str, path: str, body=None, token: str = ""):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def _entry(expires_at: str) -> dict:
    return {
        "email": EMAIL,
        "password": "dummy",
        "tokens": {
            "access_token": "dummy-access-token",
            "refresh_token": "dummy-refresh-token",
            "id_token": "dummy-id-token",
            "expires_at": expires_at,
            "expires_in": 21600,
            "email": EMAIL,
            "display_name": "Should Not Appear",
            "scope": "openid grok-cli:access",
        },
    }


def main() -> None:
    password = "1234" + "56"
    token = _req("POST", "/auth/login", {"password": password})[
        "access_token"
    ]

    catalog = _req("GET", "/providers/catalog", token=token)
    flag = catalog["providers"][PROVIDER].get("supportsBulkImport")
    print("catalog supportsBulkImport:", flag)
    assert flag is True

    future = (
        datetime.now(timezone.utc) + timedelta(hours=6)
    ).isoformat()
    past = (
        datetime.now(timezone.utc) - timedelta(hours=6)
    ).isoformat()

    # Round 1: create + expired + invalid
    body = {
        "accounts": [
            _entry(future),
            _entry(past) | {"email": "expired@example.com"},
            {"email": "no-tokens@example.com"},
        ],
    }
    res = _req(
        "POST", f"/oauth/{PROVIDER}/bulk-import", body, token,
    )
    print("round1:", {k: res[k] for k in (
        "created", "updated", "skipped", "failed")})
    print("  statuses:", [r["status"] for r in res["results"]])
    assert res["created"] == 1 and res["skipped"] == 1
    assert res["failed"] == 1

    # Round 2: duplicate without replace -> skipped
    res = _req(
        "POST", f"/oauth/{PROVIDER}/bulk-import",
        {"accounts": [_entry(future)]}, token,
    )
    print("round2:", res["results"][0]["status"])
    assert res["skipped"] == 1
    assert res["results"][0]["status"] == "skipped_duplicate"

    # Round 3: duplicate with replace -> updated
    res = _req(
        "POST", f"/oauth/{PROVIDER}/bulk-import?replace=true",
        {"accounts": [_entry(future)]}, token,
    )
    print("round3:", res["results"][0]["status"])
    assert res["updated"] == 1

    # Find + delete the throwaway connection
    conns = _req("GET", "/providers/client", token=token)
    items = conns if isinstance(conns, list) else conns.get(
        "connections", [],
    )
    match = [c for c in items if c.get("email") == EMAIL]
    assert len(match) == 1, f"expected 1 conn, got {len(match)}"
    conn = match[0]
    print("connection:", conn.get("id"), "| name:", conn.get("name"))
    assert conn.get("name") == EMAIL
    _req("DELETE", f"/providers/{conn['id']}", token=token)

    conns = _req("GET", "/providers/client", token=token)
    items = conns if isinstance(conns, list) else conns.get(
        "connections", [],
    )
    assert not [c for c in items if c.get("email") == EMAIL]
    print("cleanup: connection deleted")
    print("ALL BULK IMPORT CHECKS PASSED")


if __name__ == "__main__":
    main()
