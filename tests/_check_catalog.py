#!/usr/bin/env python3
"""Scratch: dump grok-cli catalog entry."""

import json
import urllib.request

BASE = "http://localhost:8013"


def main() -> None:
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

    req = urllib.request.Request(
        BASE + "/providers/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    entry = data["providers"].get("grok-cli")
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()
