#!/usr/bin/env python3
"""QA Test Script: Fetch Models, Clear Models, Enable All"""
import json
import subprocess
import sys
import time

BASE = "http://localhost:9000"

def curl(method, path, data=None, token=None):
    """Make a curl request and return parsed JSON."""
    cmd = ["curl", "-s", "-X", method, f"{BASE}{path}", "-H", "Content-Type: application/json"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if data:
        cmd += ["-d", json.dumps(data)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout, "stderr": result.stderr}

def get_token():
    resp = curl("POST", "/auth/login", {"password": "123456"})
    return resp["access_token"]

def get_providers(token):
    return curl("GET", "/providers", token=token)

def main():
    token = get_token()
    print(f"=== TOKEN OK ===")
    
    providers = get_providers(token)
    
    # Group by provider type
    by_type = {}
    for p in providers:
        prov = p["provider"]
        if prov not in by_type:
            by_type[prov] = []
        by_type[prov].append(p)
    
    # Pick test targets
    print("\n=== PROVIDER SUMMARY ===")
    for prov, conns in sorted(by_type.items()):
        total_models = sum(len(c.get("models", [])) for c in conns)
        print(f"  {prov}: {len(conns)} connections, {total_models} total models")
    
    # Select cerebras (has 2 connections with 4 models each)
    cerebras = by_type.get("cerebras", [])
    gemini = by_type.get("gemini", [])
    groq = by_type.get("groq", [])
    
    print(f"\n=== TEST TARGETS ===")
    if cerebras:
        c = cerebras[0]
        print(f"CEREBRAS_TEST_ID={c['id']}")
        print(f"CEREBRAS_TEST_MODELS={json.dumps(c.get('models', []))}")
        print(f"CEREBRAS_TEST_MODELS_COUNT={len(c.get('models', []))}")
    if gemini:
        g = gemini[0]
        print(f"GEMINI_TEST_ID={g['id']}")
        print(f"GEMINI_TEST_MODELS_COUNT={len(g.get('models', []))}")
    if groq:
        gr = groq[0]
        print(f"GROQ_TEST_ID={gr['id']}")
        print(f"GROQ_TEST_MODELS_COUNT={len(gr.get('models', []))}")
    
    # Print all connection IDs grouped by provider
    print(f"\n=== ALL CONNECTIONS ===")
    for prov, conns in sorted(by_type.items()):
        print(f"\n{prov}:")
        for c in conns:
            print(f"  {c['id']} | {c['name']} | models={len(c.get('models', []))} | active={c.get('is_active')}")

if __name__ == "__main__":
    main()
