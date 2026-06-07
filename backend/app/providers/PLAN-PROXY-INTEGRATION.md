# Proxy Integration — Pindahkan Provider-Specific Logic dari proxy.py ke Handler

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Pindahkan semua provider-specific logic dari `services/proxy.py` dan `v1_proxy/shared.py` ke masing-masing provider handler, sehingga proxy layer menjadi generic dispatcher.

**Architecture:** Tambah method `build_upstream_url()`, `build_headers()`, `build_embeddings_url()`, `build_embeddings_body()` ke `BaseProviderHandler`. Override di handler provider-specific. Proxy dispatch ke handler.

---

## Problem

`services/proxy.py` (900 baris) mengandung provider-specific logic di beberapa fungsi:

| Fungsi | Provider-Specific | Baris |
|--------|-------------------|-------|
| `_build_upstream_url()` | claude, gemini, azure, cloudflare, qoder | ~20 if/elif |
| `_build_headers()` | qoder (COSY signing) | ~25 if/elif |
| `_resolve_base_url()` | xiaomi-tokenplan (region) | ~10 if |

`v1_proxy/shared.py` juga mengandung:

| Fungsi | Provider-Specific | Baris |
|--------|-------------------|-------|
| `_build_embeddings_url()` | gemini (`embedContent`) | ~10 if |
| `_build_embeddings_body()` | gemini (`content.parts`) | ~10 if |
| `_non_stream_response()` | qoder (unwrap envelope) | ~5 if |

**Akibat:**
- Tambah provider dengan format berbeda = edit `proxy.py`
- Provider-specific code bercampur dengan generic routing logic
- Sulit test individual provider URL building

**Solusi:** Setiap provider punya handler yang handle URL building, header building, dan body transformation. Proxy tinggal dispatch.

---

## Current State → Target State

### Current (if/elif chain di proxy.py):

```python
def _build_upstream_url(provider, base_url, stream, data, model):
    cfg = _get_provider_proxy_config(provider)
    fmt = cfg["format"]
    
    if fmt == "claude":
        return f"{base}/messages"
    elif fmt == "gemini":
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        return f"{base}/models/{model}:{action}"
    elif fmt == "azure":
        endpoint = data.get("azureEndpoint") or base
        deployment = data.get("deployment", "gpt-4")
        return f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=..."
    elif provider == "cloudflare-ai":
        account_id = data.get("accountId", "")
        return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    elif provider == "qoder":
        return f"{base}/algo/api/v2/service/pro/sse/agent_chat_generation?..."
    else:
        return f"{base}/chat/completions"
```

### Target (dispatch ke handler):

```python
def _build_upstream_url(provider, base_url, stream, data, model):
    p = Provider(provider)
    handler = p.handler()
    return handler.build_upstream_url(base_url, stream, data, model)
```

---

## File Structure

### Modified Files

| File | Change |
|------|--------|
| `backend/app/providers/base.py` | Add 4 new methods ke `BaseProviderHandler` |
| `backend/app/providers/anthropic/handler.py` | Override `build_upstream_url()` |
| `backend/app/providers/gemini/handler.py` | Override `build_upstream_url()`, `build_embeddings_url()`, `build_embeddings_body()` |
| `backend/app/providers/azure/handler.py` | Override `build_upstream_url()` |
| `backend/app/providers/cloudflare_ai/handler.py` | Override `build_upstream_url()` |
| `backend/app/providers/qoder/handler.py` | Override `build_upstream_url()`, `build_headers()`, `unwrap_response()` |
| `backend/app/services/proxy.py` | Replace if/elif chains with handler dispatch |
| `backend/app/routers/v1_proxy/shared.py` | Replace provider-specific logic with handler dispatch |

### Files NOT Modified

| File | Reason |
|------|--------|
| Other provider handlers | Tidak perlu override — default OpenAI-compatible sudah cukup |

---

## New Handler Methods

### 1. `build_upstream_url(base_url, stream, data, model) → str`

Build the full upstream URL for chat/completions requests.

**Default implementation (OpenAI-compatible):**
```python
def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
    return f"{base_url.rstrip('/')}/chat/completions"
```

**Overrides needed:**
- `anthropic`: `{base}/messages`
- `gemini`: `{base}/models/{model}:generateContent` (or `streamGenerateContent?alt=sse`)
- `azure`: `{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}`
- `cloudflare-ai`: `https://api.cloudflare.com/client/v4/accounts/{accountId}/ai/v1/chat/completions`
- `qoder`: `{base}/algo/api/v2/service/pro/sse/agent_chat_generation?...`

### 2. `build_headers(api_key, stream, data) → dict[str, str]`

Build HTTP headers for upstream request.

**Default implementation:**
```python
def build_headers(self, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    headers[self.config.AUTH_HEADER] = f"{self.config.AUTH_PREFIX}{api_key}"
    if self.config.EXTRA_HEADERS:
        headers.update(self.config.EXTRA_HEADERS)
    if stream:
        headers["Accept"] = "text/event-stream"
    return headers
```

**Overrides needed:**
- `qoder`: COSY-signed headers (complex logic)

### 3. `build_embeddings_url(chat_url) → str`

Transform chat/completions URL to embeddings URL.

**Default implementation:**
```python
def build_embeddings_url(self, chat_url: str) -> str:
    if chat_url.endswith("/chat/completions"):
        return chat_url[:-len("/chat/completions")] + "/embeddings"
    return chat_url.rstrip("/") + "/embeddings"
```

**Overrides needed:**
- `gemini`: `generateContent` → `embedContent`

### 4. `build_embeddings_body(model, body) → dict`

Transform embeddings request body for provider-specific formats.

**Default implementation:**
```python
def build_embeddings_body(self, model: str, body: dict) -> dict:
    return {**body, "model": model}
```

**Overrides needed:**
- `gemini`: `content.parts` format

### 5. `unwrap_response(response_text) → dict`

Unwrap provider-specific response envelope.

**Default implementation:**
```python
def unwrap_response(self, response_text: str) -> dict:
    return json.loads(response_text)
```

**Overrides needed:**
- `qoder`: Unwrap `{"statusCodeValue":200,"body":"..."}` envelope

---

## Tasks

### Task 1: Add new methods ke BaseProviderHandler

**Files:**
- Modify: `backend/app/providers/base.py`

- [ ] **Step 1: Add 5 new methods ke BaseProviderHandler**

Tambah setelah `_normalize_model()`:

```python
    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Build the full upstream URL for chat/completions requests.

        Override in child class for provider-specific URL formats.
        Default: OpenAI-compatible /chat/completions
        """
        return f"{base_url.rstrip('/')}/chat/completions"

    def build_headers(self, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
        """Build HTTP headers for upstream request.

        Override in child class for provider-specific auth (e.g. Qoder COSY).
        Default: standard auth header from config.
        """
        if not api_key:
            raise ValueError(f"No API key configured for provider \"{self.config.PROVIDER_ID}\"")

        headers = {"Content-Type": "application/json"}
        headers[self.config.AUTH_HEADER] = f"{self.config.AUTH_PREFIX}{api_key}"
        if self.config.EXTRA_HEADERS:
            headers.update(self.config.EXTRA_HEADERS)
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def build_embeddings_url(self, chat_url: str) -> str:
        """Transform chat/completions URL to embeddings URL.

        Override in child class for provider-specific embeddings endpoints.
        Default: /chat/completions → /embeddings
        """
        if chat_url.endswith("/chat/completions"):
            return chat_url[:-len("/chat/completions")] + "/embeddings"
        if "/chat/completions" in chat_url:
            return chat_url.replace("/chat/completions", "/embeddings")
        return chat_url.rstrip("/") + "/embeddings"

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Transform embeddings request body for provider-specific formats.

        Override in child class for non-OpenAI formats (e.g. Gemini).
        Default: pass through with model override.
        """
        return {**body, "model": model}

    def unwrap_response(self, response_text: str) -> dict:
        """Unwrap provider-specific response envelope.

        Override in child class for providers with custom envelopes (e.g. Qoder).
        Default: standard JSON parse.
        """
        return json.loads(response_text)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/base.py
git commit -m "feat(providers): add proxy methods to BaseProviderHandler"
```

---

### Task 2: Override build_upstream_url() di Anthropic handler

**Files:**
- Modify: `backend/app/providers/anthropic/handler.py`

- [ ] **Step 1: Add method**

```python
    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Anthropic uses /messages endpoint."""
        return f"{base_url.rstrip('/')}/messages"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/anthropic/handler.py
git commit -m "feat(anthropic): override build_upstream_url for /messages"
```

---

### Task 3: Override build_upstream_url(), build_embeddings_url(), build_embeddings_body() di Gemini handler

**Files:**
- Modify: `backend/app/providers/gemini/handler.py`

- [ ] **Step 1: Add methods**

```python
    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Gemini uses /models/{model}:generateContent format."""
        base = base_url.rstrip("/")
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        model_id = model.replace("models/", "") if model else ""
        if model_id:
            return f"{base}/models/{model_id}:{action}"
        return f"{base}/models"

    def build_embeddings_url(self, chat_url: str) -> str:
        """Gemini uses embedContent instead of /embeddings."""
        if ":generateContent" in chat_url:
            return chat_url.replace(":generateContent", ":embedContent")
        return super().build_embeddings_url(chat_url)

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Gemini uses content.parts format for embeddings."""
        input_text = body.get("input", "")
        if isinstance(input_text, list):
            input_text = " ".join(str(x) for x in input_text)
        return {
            "model": model,
            "content": {"parts": [{"text": str(input_text)}]},
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/gemini/handler.py
git commit -m "feat(gemini): override URL and body building for Gemini API"
```

---

### Task 4: Override build_upstream_url() di Azure handler

**Files:**
- Modify: `backend/app/providers/azure/handler.py`

- [ ] **Step 1: Add method**

```python
    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Azure uses deployments format with api-version."""
        data = data or {}
        endpoint = data.get("azureEndpoint") or base_url
        deployment = data.get("deployment", "gpt-4")
        api_version = data.get("apiVersion", "2024-10-01-preview")
        return f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/azure/handler.py
git commit -m "feat(azure): override build_upstream_url for deployments"
```

---

### Task 5: Override build_upstream_url() di Cloudflare AI handler

**Files:**
- Modify: `backend/app/providers/cloudflare_ai/handler.py`

- [ ] **Step 1: Add method**

```python
    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Cloudflare AI uses account-based URL."""
        data = data or {}
        account_id = data.get("accountId", "")
        return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/cloudflare_ai/handler.py
git commit -m "feat(cloudflare-ai): override build_upstream_url for account-based URL"
```

---

### Task 6: Buat Qoder handler dengan full overrides

**Files:**
- Create: `backend/app/providers/qoder/handler.py`

- [ ] **Step 1: Create handler**

```python
"""Qoder provider handler — COSY-signed requests, custom URL/headers/envelope."""

import json

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.proxy import ALIAS_TO_ID


class QoderHandler(BaseProviderHandler):
    """Handler for Qoder provider (COSY-signed, WAF-bypass encoding)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        # Qoder validation is complex (COSY signing) — keep simple for now
        return ValidateResult(valid=True, models=None)

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Qoder uses COSY-signed endpoint with Encode=1."""
        return f"{base_url.rstrip('/')}/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1"

    def build_headers(self, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
        """Qoder uses COSY-signed headers."""
        from app.services.qoder.cosy import build_cosy_headers
        from app.services.qoder.constants import QODER_CHAT_URL_ENCODED

        data = data or {}
        user_id = data.get("userId", "")
        machine_id = data.get("machineId", "")

        if not user_id:
            raise ValueError("Qoder userId missing — cannot build COSY headers")

        # Build COSY headers with empty body - will be re-signed later in build_qoder_request()
        cosy_headers = build_cosy_headers(
            body=b"",
            request_url=QODER_CHAT_URL_ENCODED,
            user_id=user_id,
            auth_token=api_key,
            name=data.get("displayName", ""),
            email=data.get("email", ""),
            machine_id=machine_id,
        )

        if stream:
            cosy_headers["Accept"] = "text/event-stream"

        return cosy_headers

    def unwrap_response(self, response_text: str) -> dict:
        """Qoder wraps responses in an envelope."""
        from app.services.qoder.transform import unwrap_qoder_response
        return unwrap_qoder_response(response_text)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/qoder/handler.py
git commit -m "feat(qoder): add handler with COSY-signed URL/headers/envelope"
```

---

### Task 7: Refactor proxy.py — dispatch _build_upstream_url() ke handler

**Files:**
- Modify: `backend/app/services/proxy.py`

- [ ] **Step 1: Replace _build_upstream_url()**

```python
def _build_upstream_url(provider: str, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
    """Build the upstream URL for a provider using handler."""
    try:
        p = Provider(provider)
        handler = p.handler()
        return handler.build_upstream_url(base_url, stream, data or {}, model)
    except (ValueError, ModuleNotFoundError):
        # Fallback for unknown providers
        return f"{base_url.rstrip('/')}/chat/completions"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/proxy.py
git commit -m "refactor(proxy): dispatch build_upstream_url to handler"
```

---

### Task 8: Refactor proxy.py — dispatch _build_headers() ke handler

**Files:**
- Modify: `backend/app/services/proxy.py`

- [ ] **Step 1: Replace _build_headers()**

```python
def _build_headers(provider: str, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
    """Build headers for upstream provider using handler."""
    try:
        p = Provider(provider)
        handler = p.handler()
        return handler.build_headers(api_key, stream, data)
    except (ValueError, ModuleNotFoundError):
        # Fallback for unknown providers
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {api_key}"
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/proxy.py
git commit -m "refactor(proxy): dispatch build_headers to handler"
```

---

### Task 9: Refactor proxy.py — dispatch _resolve_base_url() ke handler

**Files:**
- Modify: `backend/app/services/proxy.py`

- [ ] **Step 1: Replace _resolve_base_url()**

```python
def _resolve_base_url(provider: str, data: dict | None = None) -> str:
    """Resolve base URL for a provider using handler."""
    if data is None:
        data = {}

    # Check if custom baseUrl is provided in connection data
    if data.get("baseUrl"):
        return data["baseUrl"]

    try:
        p = Provider(provider)
        return p.resolve_base_url(data)
    except (ValueError, ModuleNotFoundError):
        cfg = _get_provider_proxy_config(provider)
        return cfg.get("base_url", "")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/proxy.py
git commit -m "refactor(proxy): dispatch resolve_base_url to handler"
```

---

### Task 10: Refactor shared.py — dispatch embeddings logic ke handler

**Files:**
- Modify: `backend/app/routers/v1_proxy/shared.py`

- [ ] **Step 1: Replace _build_embeddings_url()**

```python
def _build_embeddings_url(target: ProxyTarget) -> str:
    """Derive the embeddings endpoint URL using handler."""
    try:
        from app.providers.provider import Provider
        p = Provider(target.provider)
        handler = p.handler()
        return handler.build_embeddings_url(target.url)
    except (ValueError, ModuleNotFoundError):
        # Fallback: standard OpenAI-compat
        if target.url.endswith("/chat/completions"):
            return target.url[:-len("/chat/completions")] + "/embeddings"
        return target.url.rstrip("/") + "/embeddings"
```

- [ ] **Step 2: Replace _build_embeddings_body()**

```python
def _build_embeddings_body(target: ProxyTarget, body: dict) -> dict:
    """Transform the embeddings request body using handler."""
    try:
        from app.providers.provider import Provider
        p = Provider(target.provider)
        handler = p.handler()
        return handler.build_embeddings_body(target.model, body)
    except (ValueError, ModuleNotFoundError):
        # Fallback: standard OpenAI-compat
        return {**body, "model": target.model}
```

- [ ] **Step 3: Replace Qoder unwrap in _non_stream_response()**

```python
        # Unwrap provider-specific response envelope
        try:
            from app.providers.provider import Provider
            p = Provider(target.provider)
            handler = p.handler()
            data = handler.unwrap_response(resp.text)
        except Exception:
            # Fallback: standard JSON parse
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/v1_proxy/shared.py
git commit -m "refactor(shared): dispatch embeddings and response unwrapping to handler"
```

---

### Task 11: Cleanup — remove unused _get_provider_proxy_config() callers

**Files:**
- Modify: `backend/app/services/proxy.py`

- [ ] **Step 1: Check if _get_provider_proxy_config() is still needed**

After Tasks 7-9, `_get_provider_proxy_config()` may only be used in fallback paths. Keep it as fallback but document it's legacy.

```python
def _get_provider_proxy_config(provider: str) -> dict:
    """Get provider proxy config from Provider class (LEGACY — prefer handler methods).

    Returns dict with keys: base_url, format, auth_header, auth_prefix, extra_headers.
    Used as fallback when handler is not available.
    """
    # ... existing implementation ...
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/proxy.py
git commit -m "chore(proxy): document _get_provider_proxy_config as legacy fallback"
```

---

### Task 12: Verify — run tests dan manual check

- [ ] **Step 1: Run tests**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -m pytest tests/ -v --tb=short --ignore=tests/test_provider_models-v1.py
```

- [ ] **Step 2: Verify handler loading**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -c "
from app.providers.provider import Provider

# Test new methods
for name in ['anthropic', 'gemini', 'azure', 'cloudflare-ai', 'qoder', 'openai']:
    p = Provider(name)
    h = p.handler()
    url = h.build_upstream_url('https://example.com/v1', stream=True, data={}, model='test-model')
    print(f'{name}: {url}')
"
```

Expected:
```
anthropic: https://example.com/v1/messages
gemini: https://example.com/v1/models/test-model:streamGenerateContent?alt=sse
azure: https://example.com/v1/openai/deployments/gpt-4/chat/completions?api-version=2024-10-01-preview
cloudflare-ai: https://api.cloudflare.com/client/v4/accounts//ai/v1/chat/completions
qoder: https://example.com/v1/algo/api/v2/service/pro/sse/agent_chat_generation?...
openai: https://example.com/v1/chat/completions
```

- [ ] **Step 3: Verify proxy integration**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -c "
from app.services.proxy import _build_upstream_url, _build_headers

# Test that dispatch works
url = _build_upstream_url('anthropic', 'https://api.anthropic.com/v1', stream=True, model='claude-3')
print(f'Anthropic URL: {url}')

url = _build_upstream_url('gemini', 'https://generativelanguage.googleapis.com/v1beta', stream=False, model='gemini-pro')
print(f'Gemini URL: {url}')

url = _build_upstream_url('openai', 'https://api.openai.com/v1', stream=False, model='gpt-4')
print(f'OpenAI URL: {url}')
"
```

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat(providers): complete proxy integration with handler dispatch"
```

---

## Success Criteria

1. `_build_upstream_url()` dispatches ke handler (tidak ada if/elif)
2. `_build_headers()` dispatches ke handler (tidak ada if/elif qoder)
3. `_resolve_base_url()` dispatches ke handler (tidak ada if xiaomi-tokenplan)
4. `_build_embeddings_url()` dispatches ke handler
5. `_build_embeddings_body()` dispatches ke handler
6. Response unwrapping dispatches ke handler
7. Provider tanpa custom handler tetap work (fallback ke default OpenAI-compatible)
8. Semua existing tests pass

---

## Dependency Order

```
Task 1  (base.py methods) ─────────────────────┐
Task 2-6 (handler overrides) ──────────────────┼──► Task 7-10 (refactor proxy/shared)
                                                │
Task 11 (cleanup) ─────────────────────────────┤
Task 12 (verify) ◄─────────────────────────────┘
```

Tasks 2-6 bisa parallel. Tasks 7-10 harus sequential (satu fungsi per commit).

---

## Notes

- **Qoder** adalah provider paling kompleks — punya COSY signing, WAF-bypass encoding, dan custom envelope. Handler-nya paling besar.
- **Backward compatibility:** Fungsi lama `_build_upstream_url()` dll tetap ada sebagai dispatcher, bukan dihapus.
- **Fallback:** Provider tanpa handler (misal `deepseek`, `groq`) tetap work via default `BaseProviderHandler` implementation.
- **Testing:** Setiap handler bisa di-test secara independen dengan `handler.build_upstream_url(...)`.
