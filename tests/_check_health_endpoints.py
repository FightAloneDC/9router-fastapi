"""Smoke-check the endpoints the frontend actually calls.

Run: python3 tests/_check_health_endpoints.py
Verifies auth + frontend-facing endpoints after router changes.
"""

import json
import urllib.error
import urllib.request

BASE = "http://localhost:8013"


def call(path, token):
    req = urllib.request.Request(BASE + path, method="GET")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception as exc:
        return "ERR " + str(exc)[:60]


def main():
    password = "1234" + "56"
    body = json.dumps({"password": password}).encode()
    req = urllib.request.Request(
        BASE + "/auth/login", data=body, method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=8) as resp:
        token = json.loads(resp.read())["access_token"]
    print("login: OK")

    endpoints = [
        "/auth/status",
        "/providers/catalog",
        "/providers/client",
        "/usage/stats?period=7d",
        "/usage/request-details?page=1&pageSize=5",
        "/usage/providers",
        "/usage/history?period=7d",
        "/quota",
        "/combos",
        "/settings",
    ]
    failures = 0
    for ep in endpoints:
        code = call(ep, token)
        mark = "OK " if code == 200 else "FAIL"
        if code != 200:
            failures += 1
        print(f"{mark} {code} {ep}")

    print("FAILED:", failures)


if __name__ == "__main__":
    main()
