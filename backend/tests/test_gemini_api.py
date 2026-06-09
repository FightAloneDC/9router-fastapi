"""Test Gemini API directly with correct format.

Usage:
    python tests/test_gemini_api.py YOUR_API_KEY
    python tests/test_gemini_api.py   # uses default key
"""
import httpx
import json
import sys

base_url = "https://generativelanguage.googleapis.com/v1beta"
model = "gemini-3.1-flash-lite"
url = f"{base_url}/models/{model}:generateContent"

api_key = sys.argv[1] if len(sys.argv) > 1 else ""

headers = {"Content-Type": "application/json"}

body = {
    "contents": [{"parts": [{"text": "hi"}], "role": "user"}],
    "generationConfig": {"maxOutputTokens": 10},
}

print(f"URL: {url}")
print(f"Body: {json.dumps(body, indent=2)}")

resp = httpx.post(url, headers=headers, json=body, params={"key": api_key}, timeout=30)

print(f"Status: {resp.status_code}")
print(f"Response type: {type(resp.json()).__name__}")
print(f"Response:\n{json.dumps(resp.json(), indent=2, ensure_ascii=False)}")

# Save to file
output_filename = "output2.txt"
with open(output_filename, "w") as f:
    f.write(f"Status: {resp.status_code}\n")
    f.write(f"Response type: {type(resp.json()).__name__}\n")
    f.write(f"Response:\n{json.dumps(resp.json(), indent=2, ensure_ascii=False)}\n")

print(f"\nSaved to {output_filename}")
