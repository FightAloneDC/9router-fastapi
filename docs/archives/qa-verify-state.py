#!/usr/bin/env python3
"""Verify all test data is restored to baseline"""
import json
import subprocess

BASE = "http://localhost:9000"

def curl(method, path, token=None):
    cmd = ["curl", "-s", "-X", method, f"{BASE}{path}", "-H", "Content-Type: application/json"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except:
        return {"raw": result.stdout}

# Login
login = curl("POST", "/auth/login", {"password": "123456"})
token = login["access_token"]

# Get all providers
providers = curl("GET", "/providers", token=token)

# Check state
print("=== CURRENT STATE ===")
by_type = {}
for p in providers:
    prov = p["provider"]
    if prov not in by_type:
        by_type[prov] = []
    by_type[prov].append(p)

for prov, conns in sorted(by_type.items()):
    for c in conns:
        models = c.get("models", [])
        print(f"  {prov} / {c['name'][:25]:25s} | {c['id'][:12]} | models={len(models):3d}")

# Check disabled
for prov in ["gemini", "groq", "cerebras"]:
    disabled = curl("GET", f"/models/disabled?providerAlias={prov}", token=token)
    ids = disabled.get("ids", [])
    if ids:
        print(f"\n  WARNING: {prov} has {len(ids)} disabled models: {ids}")
