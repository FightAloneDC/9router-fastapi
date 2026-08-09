#!/usr/bin/env python3
"""Scratch: list provider connections via JWT login."""

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
        BASE + "/providers/client",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    conns = data if isinstance(data, list) else data.get("connections", [])
    print("connections:", len(conns))
    for c in conns[:20]:
        models = c.get("models") or []
        print(
            " -", c.get("provider"),
            "| active:", c.get("isActive"),
            "| models:", len(models),
            "| test:", c.get("testStatus"),
        )


if __name__ == "__main__":
    main()
