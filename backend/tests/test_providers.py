#!/usr/bin/env python3
"""
Test script untuk testing provider satu-satu via OpenAI-compatible API
Menggunakan httpx yang sudah ada di dependencies, tidak perlu install tambahan
"""
import httpx
import json
import sys
from typing import Optional

# Backend API base URL
BACKEND_URL = "http://localhost:9000"
ADMIN_PASSWORD = "123456"

def get_auth_token() -> str:
    """Login dan dapatkan auth token"""
    response = httpx.post(
        f"{BACKEND_URL}/auth/login",
        json={"password": ADMIN_PASSWORD},
        timeout=10.0
    )
    response.raise_for_status()
    return response.json()["access_token"]

def get_active_providers(token: str) -> list:
    """Ambil list provider yang aktif"""
    response = httpx.get(
        f"{BACKEND_URL}/providers",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0
    )
    response.raise_for_status()
    return [p for p in response.json() if p["is_active"]]

def test_provider_chat(
    provider_id: str,
    model_id: str,
    base_url: str,
    api_key: Optional[str] = None,
    message: str = "Hello, respond with just 'OK' if you can read this."
) -> dict:
    """Test provider dengan chat completion request"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "provider": provider_id,
            "model": model_id,
            "response": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
            "usage": data.get("usage", {}),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "provider": provider_id,
            "model": model_id,
            "response": None,
            "usage": None,
            "error": str(e)
        }

def main():
    print("=== 9Router Provider Testing ===\n")
    
    # Login
    print("1. Authenticating...")
    try:
        token = get_auth_token()
        print("   ✓ Authenticated\n")
    except Exception as e:
        print(f"   ✗ Failed to authenticate: {e}")
        sys.exit(1)
    
    # Get active providers
    print("2. Fetching active providers...")
    try:
        providers = get_active_providers(token)
        print(f"   ✓ Found {len(providers)} active providers\n")
    except Exception as e:
        print(f"   ✗ Failed to fetch providers: {e}")
        sys.exit(1)
    
    # List providers
    print("3. Active providers:")
    for i, p in enumerate(providers, 1):
        print(f"   {i}. {p['provider']:20} - {p.get('name', 'N/A'):30} (status: {p['test_status']})")
    
    print("\n" + "="*60)
    print("Ready to test providers.")
    print("Usage: python test_providers.py [provider_id]")
    print("="*60)

if __name__ == "__main__":
    main()
