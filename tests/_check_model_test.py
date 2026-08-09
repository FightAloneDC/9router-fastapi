#!/usr/bin/env python3
"""Scratch: hit /models/test for a grok-cli model (Test Model button)."""

import json
import sys
import urllib.request

BASE = "http://localhost:8013"


def main() -> int:
    password = "1234" + "56"
    body = json.dumps({"password": password}).encode()
    req = urllib.request.Request(
        BASE + "/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = json.loads(
        urllib.request.urlopen(req, timeout=15).read(),
    )["access_token"]

    model = sys.argv[1] if len(sys.argv) > 1 else "gcli/grok-build"
    req = urllib.request.Request(
        BASE + "/models/test",
        data=json.dumps({"model": model}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:300]}")
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
