#!/usr/bin/env python3
"""Reproduce Test 2 failure in isolation"""
import json
import subprocess

BASE = "http://localhost:9000"
CONN_ID = "c3080383-71b8-4084-bafa-69d4d25334e3"

def curl(method, path, data=None, token=None):
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", method, f"{BASE}{path}", "-H", "Content-Type: application/json"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if data is not None:
        cmd += ["-d", json.dumps(data)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    lines = result.stdout.strip().split("\n")
    status_code = int(lines[-1]) if lines[-1].isdigit() else 0
    body = "\n".join(lines[:-1])
    try:
        return status_code, json.loads(body)
    except json.JSONDecodeError:
        return status_code, {"raw": body}

# Login
_, login = curl("POST", "/auth/login", {"password": "123456"})
token = login["access_token"]

# Step 1: Get current state
code, conn = curl("GET", f"/providers/{CONN_ID}", token=token)
print(f"=== STEP 1: Current state ===")
print(f"  HTTP {code}")
print(f"  models: {conn.get('models', [])}")
print(f"  models count: {len(conn.get('models', []))}")

# Step 2: Fetch models from API
code2, fetch = curl("GET", f"/providers/{CONN_ID}/models", token=token)
print(f"\n=== STEP 2: Fetch models ===")
print(f"  HTTP {code2}")
models_raw = fetch.get("models", [])
print(f"  raw count: {len(models_raw)}")
if models_raw:
    print(f"  first model: {models_raw[0]}")
    print(f"  type: {type(models_raw[0])}")
    model_ids = [m["id"] if isinstance(m, dict) else m for m in models_raw]
    print(f"  extracted ids: {model_ids}")
else:
    print(f"  Full response: {json.dumps(fetch, indent=2)[:500]}")
    model_ids = []

# Step 3: PATCH with models
if model_ids:
    print(f"\n=== STEP 3: PATCH with {len(model_ids)} models ===")
    patch_body = {"models": model_ids}
    print(f"  Body: {json.dumps(patch_body)}")
    code3, patch_resp = curl("PATCH", f"/providers/{CONN_ID}", patch_body, token=token)
    print(f"  HTTP {code3}")
    print(f"  Response models: {patch_resp.get('models', 'MISSING')}")
    print(f"  Response models count: {len(patch_resp.get('models', []))}")

# Step 4: Verify persistence
code4, verify = curl("GET", f"/providers/{CONN_ID}", token=token)
print(f"\n=== STEP 4: Verify persistence ===")
print(f"  HTTP {code4}")
print(f"  models: {verify.get('models', [])}")
print(f"  models count: {len(verify.get('models', []))}")

# Step 5: Try with explicit simple models
print(f"\n=== STEP 5: PATCH with simple test strings ===")
test_models = ["test-model-x", "test-model-y"]
code5, patch5 = curl("PATCH", f"/providers/{CONN_ID}", {"models": test_models}, token=token)
print(f"  HTTP {code5}")
print(f"  Response models: {patch5.get('models', 'MISSING')}")

code6, verify6 = curl("GET", f"/providers/{CONN_ID}", token=token)
print(f"  After re-read: {verify6.get('models', [])}")
