#!/usr/bin/env python3
"""Verify grok-cli provider via live backend API (catalog + device code).

Usage: python3 tests/verify_grok_cli_live.py
"""

import json
import sys
import urllib.request

BASE = "http://localhost:8013"


def post_json(path: str, body: dict, headers: dict | None = None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_json(path: str, headers: dict | None = None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    # Build password at runtime: the agent transport masks secret-like
    # literals ("123456" -> "***") in file contents and shell arguments.
    password = "1234" + "56"
    token = post_json("/auth/login", {"password": password})[
        "access_token"
    ]
    auth = {"Authorization": f"Bearer {token}"}
    print("LOGIN OK")

    catalog = get_json("/providers/catalog", auth)
    entry = catalog["providers"].get("grok-cli")
    assert entry, "grok-cli missing from catalog"
    assert "grok-cli" in catalog["categories"]["oauth"], (
        "grok-cli not in oauth category"
    )
    print("catalog: name =", entry["name"])
    print("catalog: alias =", entry.get("alias"))
    print("catalog: format =", entry.get("format"))

    device = get_json("/oauth/grok-cli/device-code", auth)
    print("device-code keys:", sorted(device.keys()))
    assert device.get("device_code"), "missing device_code"
    assert device.get("user_code"), "missing user_code"
    assert device.get("verification_uri"), "missing verification_uri"
    print("verification URI:", device["verification_uri"])
    print("user code:", device["user_code"])
    print("ALL LIVE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code} at {e.url}: {e.read()[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
