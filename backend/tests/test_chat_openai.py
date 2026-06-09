#!/usr/bin/env python3
"""
9Router FastAPI — OpenAI Compatible Chat Test Script

Tests the /v1/chat/completions proxy endpoint using the openai Python SDK.
Routes through various providers configured in 9router.

Usage:
    cd /home/mint/dev/9router-fastapi
    uv run python scripts/test_chat_openai.py

Options:
    --stream        Test streaming mode
    --model MODEL   Test specific model (default: test multiple)
    --provider PROV Test specific provider alias (e.g. ds, gq, openrouter)
    --all           Test ALL active providers
"""

import sys
import time
import argparse
import json

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package not installed.")
    print("Run: uv add openai")
    sys.exit(1)

# ─── Config ──────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:1455/v1"
API_KEY = "dummy"  # requireApiKey=false, any value works

# Provider alias → display name
PROVIDERS = {
    "ds":           ("deepseek",    "deepseek-chat"),
    "gq":           ("groq",        "llama-3.3-70b-versatile"),
    "openrouter":   ("openrouter",  "openai/gpt-4o-mini"),
    "mi":           ("mistral",     "mistral-small-latest"),
    "mimo":         ("xiaomi-mimo", "mimo-v2.5-pro"),
    "kr":           ("kiro",        "kiro/claude-sonnet-4"),
    "gemini":       ("gemini",      "gemini-2.0-flash"),
    "nvidia":       ("nvidia",      "meta/llama-3.3-70b-instruct"),
    "cerebras":     ("cerebras",    "llama-3.3-70b"),
    "cohere":       ("cohere",      "command-r-plus"),
    "oc":           ("opencode",    "opencode/deepseek-v4-flash"),
    "kg":           ("kilo-gateway","kilo-auto/balanced"),
}

TEST_PROMPT = "Say hello in one sentence. Be brief."

# ─── Helpers ─────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")


def info(msg):
    print(f"  {CYAN}→{RESET} {msg}")


def section(title):
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_connection(client: OpenAI) -> bool:
    """Test basic connectivity to proxy."""
    section("1. Connection Test")
    try:
        models = client.models.list()
        model_count = len(models.data)
        ok(f"Connected to {BASE_URL}")
        ok(f"Models available: {model_count}")
        return True
    except Exception as e:
        fail(f"Connection failed: {e}")
        return False


def test_list_models(client: OpenAI):
    """List available models grouped by owner."""
    section("2. Available Models")
    try:
        models = client.models.list()
        
        # Group by owned_by
        by_owner = {}
        for m in models.data:
            owner = getattr(m, 'owned_by', 'unknown')
            if owner not in by_owner:
                by_owner[owner] = []
            by_owner[owner].append(m.id)
        
        for owner, model_ids in sorted(by_owner.items()):
            info(f"{BOLD}{owner}{RESET} ({len(model_ids)} models)")
            for mid in model_ids[:5]:
                print(f"      {mid}")
            if len(model_ids) > 5:
                print(f"      ... and {len(model_ids) - 5} more")
        
        return models.data
    except Exception as e:
        fail(f"Failed to list models: {e}")
        return []


def test_chat_completion(client: OpenAI, model: str, stream: bool = False) -> dict:
    """Test a single chat completion request."""
    result = {
        "model": model,
        "stream": stream,
        "success": False,
        "response": None,
        "latency_ms": 0,
        "tokens": {},
        "error": None,
    }
    
    try:
        start = time.time()
        
        if stream:
            # Streaming test
            stream_resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": TEST_PROMPT}],
                max_tokens=100,
                stream=True,
            )
            
            chunks = []
            for chunk in stream_resp:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
            
            elapsed = (time.time() - start) * 1000
            full_text = "".join(chunks)
            
            result["response"] = full_text
            result["latency_ms"] = round(elapsed)
            result["success"] = len(full_text) > 0
            
        else:
            # Non-streaming test
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": TEST_PROMPT}],
                max_tokens=100,
            )
            
            elapsed = (time.time() - start) * 1000
            text = resp.choices[0].message.content if resp.choices else ""
            
            result["response"] = text
            result["latency_ms"] = round(elapsed)
            result["success"] = len(text) > 0
            
            if resp.usage:
                result["tokens"] = {
                    "prompt": resp.usage.prompt_tokens,
                    "completion": resp.usage.completion_tokens,
                    "total": resp.usage.total_tokens,
                }
    
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        result["latency_ms"] = round(elapsed)
        result["error"] = str(e)[:200]
    
    return result


def test_provider(alias: str, client: OpenAI, stream: bool = False):
    """Test a specific provider."""
    if alias not in PROVIDERS:
        fail(f"Unknown provider alias: {alias}")
        info(f"Available: {', '.join(PROVIDERS.keys())}")
        return None
    
    provider_name, default_model = PROVIDERS[alias]
    model = default_model
    
    mode_label = "stream" if stream else "sync"
    info(f"Testing {BOLD}{provider_name}{RESET} ({alias}) — model: {model} [{mode_label}]")
    
    result = test_chat_completion(client, model, stream)
    
    if result["success"]:
        response_preview = result["response"][:80].replace("\n", " ")
        ok(f"Response ({result['latency_ms']}ms): \"{response_preview}\"")
        if result["tokens"]:
            info(f"Tokens: {result['tokens']['prompt']}+{result['tokens']['completion']}={result['tokens']['total']}")
    else:
        err = result["error"] or "Empty response"
        fail(f"Failed ({result['latency_ms']}ms): {err}")
    
    return result


def test_all_providers(client: OpenAI, stream: bool = False):
    """Test all configured providers."""
    section("3. Provider Tests" + (" [STREAMING]" if stream else " [NON-STREAMING]"))
    
    results = []
    for alias in PROVIDERS:
        result = test_provider(alias, client, stream)
        if result:
            results.append(result)
        print()  # spacing
    
    return results


def test_error_handling(client: OpenAI):
    """Test error cases."""
    section("4. Error Handling")
    
    # Test missing model
    info("Test: Missing model field")
    try:
        import httpx
        resp = httpx.post(
            f"{BASE_URL}/chat/completions",
            json={"messages": [{"role": "user", "content": "test"}]},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        if resp.status_code == 400:
            ok(f"Missing model → 400 Bad Request (correct)")
        else:
            warn(f"Missing model → {resp.status_code} (expected 400)")
    except Exception as e:
        fail(f"Error: {e}")
    
    # Test invalid model
    info("Test: Non-existent model")
    try:
        resp = client.chat.completions.create(
            model="nonexistent/fake-model-xyz",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10,
        )
        warn(f"Invalid model returned response (expected error)")
    except Exception as e:
        err_str = str(e)[:100]
        if "503" in err_str or "No provider" in err_str or "404" in err_str:
            ok(f"Invalid model → error (correct): {err_str}")
        else:
            warn(f"Invalid model → unexpected error: {err_str}")
    
    # Test empty messages
    info("Test: Empty messages array")
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[],
            max_tokens=10,
        )
        warn(f"Empty messages returned response (expected error)")
    except Exception as e:
        err_str = str(e)[:100]
        ok(f"Empty messages → error (correct): {err_str}")


def print_summary(results: list):
    """Print final summary table."""
    section("Summary")
    
    if not results:
        warn("No results to summarize")
        return
    
    print(f"  {'Provider':<20} {'Mode':<8} {'Status':<8} {'Latency':<10} {'Tokens':<10}")
    print(f"  {'─' * 20} {'─' * 8} {'─' * 8} {'─' * 10} {'─' * 10}")
    
    passed = 0
    failed = 0
    
    for r in results:
        status = f"{GREEN}PASS{RESET}" if r["success"] else f"{RED}FAIL{RESET}"
        mode = "stream" if r["stream"] else "sync"
        latency = f"{r['latency_ms']}ms"
        tokens = str(r["tokens"].get("total", "-")) if r["tokens"] else "-"
        
        if r["success"]:
            passed += 1
        else:
            failed += 1
        
        print(f"  {r['model']:<20} {mode:<8} {status:<8} {latency:<10} {tokens:<10}")
    
    print()
    print(f"  {GREEN}Passed: {passed}{RESET}  {RED}Failed: {failed}{RESET}  Total: {len(results)}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="9Router OpenAI Compatible Chat Test")
    parser.add_argument("--stream", action="store_true", help="Test streaming mode")
    parser.add_argument("--model", type=str, help="Test specific model")
    parser.add_argument("--provider", type=str, help="Test specific provider alias")
    parser.add_argument("--all", action="store_true", help="Test all providers (sync + stream)")
    parser.add_argument("--list", action="store_true", help="List models only")
    parser.add_argument("--url", type=str, default=BASE_URL, help="Override base URL")
    args = parser.parse_args()
    
    url = args.url
    
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"  {BOLD}9Router — OpenAI Compatible Chat Test{RESET}")
    print(f"  URL: {url}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    
    client = OpenAI(base_url=url, api_key=API_KEY)
    
    # 1. Connection
    if not test_connection(client):
        print(f"\n{RED}Cannot connect to proxy. Is the backend running?{RESET}")
        print(f"  Check: docker ps | grep 9router-backend")
        print(f"  Start: cd /home/mint/dev/9router-fastapi && docker compose -f docker-compose.dev.yml up -d")
        sys.exit(1)
    
    # 2. List models
    test_list_models(client)
    
    if args.list:
        return
    
    # 3. Provider tests
    if args.model:
        # Single model test
        section(f"3. Single Model Test: {args.model}")
        result = test_chat_completion(client, args.model, args.stream)
        if result["success"]:
            ok(f"Response ({result['latency_ms']}ms): {result['response'][:100]}")
        else:
            fail(f"Failed: {result['error']}")
    
    elif args.provider:
        # Single provider test
        section(f"3. Provider Test: {args.provider}")
        test_provider(args.provider, client, args.stream)
    
    elif args.all:
        # All providers - both sync and stream
        results_sync = test_all_providers(client, stream=False)
        results_stream = test_all_providers(client, stream=True)
        print_summary(results_sync + results_stream)
    
    else:
        # Default: test a few key providers (non-streaming)
        section("3. Quick Smoke Test (non-streaming)")
        quick_tests = ["ds", "gq", "openrouter", "mimo"]
        results = []
        for alias in quick_tests:
            result = test_provider(alias, client, stream=False)
            if result:
                results.append(result)
            print()
        
        # Quick streaming test with one provider
        section("4. Quick Streaming Test")
        result = test_provider("ds", client, stream=True)
        if result:
            results.append(result)
        
        # Error handling
        test_error_handling(client)
        
        print_summary(results)
    
    print()


if __name__ == "__main__":
    main()
