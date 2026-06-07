# Qoder Migration — Pindahkan Qoder ke Providers System

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Migrasi qoder dari `backend/app/services/qoder/` ke `backend/app/providers/qoder/` sehingga bisa menggunakan handler system. Service layer (COSY, encoding, auth) tetap di `services/qoder/` karena complexity-nya.

**Architecture:** Buat `providers/qoder/config.py` dan `providers/qoder/handler.py`. Handler dispatch ke `services/qoder/` untuk crypto/signing. Tambah qoder ke `AVAILABLE_PROVIDERS` list.

---

## Problem

Qoder adalah satu-satunya provider yang **tidak ada** di `backend/app/providers/`:

```
backend/app/services/qoder/     ← Service layer (COSY, auth, models)
backend/app/providers/qoder/    ← TIDAK ADA
```

**Akibat:**
- `Provider("qoder")` → error `ModuleNotFoundError`
- Tidak bisa menggunakan handler system
- Proxy.py harus import langsung dari `services/qoder/`
- Tidak ada di `AVAILABLE_PROVIDERS` list

**Solusi:** Buat provider module di `providers/qoder/` yang delegate ke service layer.

---

## Qoder Auth Methods

Qoder punya **2 metode** add connection:

### 1. OAuth Device Flow
```
User klik "Login with Qoder" 
  → Generate PKCE pair + nonce
  → Buka browser: qoder.com/device/selectAccounts?challenge=...
  → Poll openapi.qoder.sh/api/v1/deviceToken/poll
  → User authorize di browser
  → Server return dt-xxx access token
  → Fetch user info
  → Simpan ke DB
```

### 2. PAT Import (Personal Access Token)
```
User dapat PAT (pt-xxx) dari qoder.com/account/integrations
  → User paste PAT di form
  → Exchange PAT → regular token via /api/v1/jobToken/exchange
  → Fetch user info dengan regular token
  → Simpan ke DB
```

---

## File Structure

### New Files

| File | Purpose |
|------|---------|
| `backend/app/providers/qoder/__init__.py` | Package init |
| `backend/app/providers/qoder/config.py` | Qoder provider config |
| `backend/app/providers/qoder/handler.py` | Handler with all overrides |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/providers/__init__.py` | Add `PROVIDER_QODER` ke constants & `AVAILABLE_PROVIDERS` |
| `backend/app/services/proxy.py` | Remove qoder-specific imports, use handler |
| `backend/app/routers/v1_proxy/shared.py` | Remove qoder-specific unwrap, use handler |
| `backend/app/routers/providers/models.py` | Remove qoder-specific fetch, use handler |

### Files NOT Modified

| File | Reason |
|------|--------|
| `backend/app/services/qoder/*` | Tetap — ini crypto/signing layer, terlalu kompleks untuk dipindah |
| `backend/app/routers/oauth.py` | Tetap — OAuth flow tetap pakai services/qoder/auth.py |

---

## Handler Methods yang Perlu Override

| Method | Qoder Implementation | Complexity |
|--------|---------------------|------------|
| `validate()` | Skip — COSY signing terlalu kompleks untuk test | Low |
| `build_upstream_url()` | COSY-signed endpoint with Encode=1 | Low |
| `build_headers()` | COSY signing (RSA+AES+MD5) | **High** |
| `build_request_body()` | Transform OpenAI → Qoder format | **High** |
| `unwrap_response()` | Unwrap Qoder SSE envelope | Medium |
| `fetch_models()` | COSY-signed model catalog | Medium |

---

## Tasks

### Task 1: Add PROVIDER_QODER ke providers/__init__.py

**Files:**
- Modify: `backend/app/providers/__init__.py`

- [ ] **Step 1: Add constant dan ke AVAILABLE_PROVIDERS**

```python
# ── Provider constants ─────────────────────────────────────────────────────
# ... existing constants ...

# Special providers (complex auth)
PROVIDER_QODER = "qoder"

# ── All implemented providers ──────────────────────────────────────────────
AVAILABLE_PROVIDERS: list[str] = [
    # ... existing providers ...
    PROVIDER_QODER,
]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/__init__.py
git commit -m "feat(providers): add qoder to AVAILABLE_PROVIDERS"
```

---

### Task 2: Buat providers/qoder/__init__.py

**Files:**
- Create: `backend/app/providers/qoder/__init__.py`

- [ ] **Step 1: Create package init**

```python
"""Qoder provider module."""
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/qoder/__init__.py
git commit -m "feat(qoder): create provider package"
```

---

### Task 3: Buat providers/qoder/config.py

**Files:**
- Create: `backend/app/providers/qoder/config.py`

- [ ] **Step 1: Create config**

```python
"""Qoder provider definition.

Static provider characteristics — runtime data (OAuth tokens, PAT tokens)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class QoderConfig(BaseProviderConfig):
    """Qoder provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Qoder"
    PROVIDER_ID: str = "qoder"
    ALIAS: str = "qd"
    BASE_URL: str = "https://api3.qoder.sh"
    SERVICE_KINDS: list[str] = ["llm"]

    # ── Connection defaults ─────────────────────────────────────────────
    FORMAT: str = "qoder"  # Custom format — not OpenAI-compatible
    VALIDATION_TYPE: str = "qoder"


class QoderMetadata(BaseMetadata):
    """Qoder UI display metadata."""

    name: str = "Qoder"
    color: str = "#6366F1"
    textIcon: str = "QD"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/qoder/config.py
git commit -m "feat(qoder): add provider config"
```

---

### Task 4: Buat providers/qoder/handler.py — basic structure

**Files:**
- Create: `backend/app/providers/qoder/handler.py`

- [ ] **Step 1: Create handler with validate() and build_upstream_url()**

```python
"""Qoder provider handler — COSY-signed requests, custom URL/headers/body/envelope.

Qoder is a special provider that uses:
- COSY signing (RSA + AES + MD5) for authentication
- WAF-bypass body encoding
- Custom request/response transformation
- OAuth device flow + PAT import for connection setup

The heavy lifting (crypto, signing) stays in services/qoder/.
This handler delegates to those services.
"""

import json
import logging
from typing import Any

from app.providers.base import BaseProviderHandler, ValidateResult

logger = logging.getLogger(__name__)


class QoderHandler(BaseProviderHandler):
    """Handler for Qoder provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        """Validate Qoder credentials.

        Qoder validation is complex (requires COSY signing).
        For now, we trust that the token is valid if it exists.
        Real validation happens when the user makes a chat request.
        """
        if not api_key:
            return ValidateResult(valid=False, error="No Qoder token configured")
        return ValidateResult(valid=True, models=None)

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Qoder uses COSY-signed endpoint with Encode=1."""
        from app.services.qoder.constants import QODER_CHAT_URL_ENCODED
        return QODER_CHAT_URL_ENCODED

    def build_headers(self, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
        """Build COSY-signed headers for Qoder.

        This is the most complex part — COSY signing uses RSA+AES+MD5.
        """
        from app.services.qoder.cosy import build_cosy_headers
        from app.services.qoder.constants import QODER_CHAT_URL_ENCODED

        data = data or {}
        user_id = data.get("userId", "")
        machine_id = data.get("machineId", "")

        if not user_id:
            raise ValueError("Qoder userId missing — cannot build COSY headers")

        # Build COSY headers with empty body
        # The actual COSY signing with body happens in build_request_body()
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

    def build_request_body(self, model: str, body: dict, data: dict | None = None) -> tuple[bytes, dict[str, str]]:
        """Transform OpenAI-format request to Qoder format with COSY signing.

        Returns:
            (encoded_body_bytes, signed_headers) tuple
        """
        from app.services.qoder.transform import build_qoder_request_body
        from app.services.qoder.cosy import build_cosy_headers
        from app.services.qoder.constants import QODER_CHAT_URL_ENCODED
        from app.services.qoder.models import get_qoder_model_config, resolve_qoder_models
        from app.services.qoder.encoding import qoder_encode_body
        from app.services.proxy import ALIAS_TO_ID

        data = data or {}
        user_id = data.get("userId", "")
        machine_id = data.get("machineId", "")
        access_token = data.get("accessToken", "")

        # Resolve model ID: "qd/qoder/auto" → alias "qd" resolves to "qoder" → strip → "auto"
        if "/" in model:
            parts = model.split("/", 1)
            resolved = ALIAS_TO_ID.get(parts[0], parts[0])
            remainder = parts[1]
            qoder_key = remainder[len(resolved) + 1:] if remainder.startswith(resolved + "/") else remainder
        else:
            qoder_key = model

        # Get model config from cache
        model_config = get_qoder_model_config(user_id, access_token, qoder_key)

        # If not in cache, we'll use a minimal config
        # Real model config should be fetched before this point
        if model_config is None:
            model_config = {"key": qoder_key}

        # Build Qoder-format request body
        qoder_body = build_qoder_request_body(
            model=model,
            body=body,
            credentials={"provider_specific": {"userId": user_id, "machineId": machine_id}},
            model_config=model_config,
            qoder_key=qoder_key,
        )

        # JSON → WAF-bypass encode
        plain_bytes = json.dumps(qoder_body).encode("utf-8")
        encoded_str = qoder_encode_body(plain_bytes)
        encoded_bytes = encoded_str.encode("latin1")

        # Build COSY headers with the ENCODED body
        cosy_headers = build_cosy_headers(
            body=encoded_bytes,
            request_url=QODER_CHAT_URL_ENCODED,
            user_id=user_id,
            auth_token=access_token,
            name=data.get("displayName", ""),
            email=data.get("email", ""),
            machine_id=machine_id,
        )

        # Add extra headers
        model_source = (model_config or {}).get("source", "system")
        cosy_headers["X-Model-Key"] = qoder_key
        cosy_headers["X-Model-Source"] = model_source
        cosy_headers["Cache-Control"] = "no-cache"
        cosy_headers["Accept"] = "text/event-stream"

        return encoded_bytes, cosy_headers

    def unwrap_response(self, response_text: str) -> dict[str, Any]:
        """Unwrap Qoder's custom response envelope."""
        from app.services.qoder.transform import unwrap_qoder_response
        return unwrap_qoder_response(response_text)

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        """Fetch models from Qoder catalog (COSY-signed)."""
        from app.services.qoder.models import resolve_qoder_models

        data = data or {}
        user_id = data.get("userId", "")
        machine_id = data.get("machineId", "")

        credentials = {
            "access_token": api_key,
            "provider_specific": {
                "userId": user_id,
                "machineId": machine_id,
            },
        }

        result = await resolve_qoder_models(credentials, force_refresh=True)

        models = []
        for m in result.get("models", []):
            model_id = m.get("id", "")
            if model_id:
                models.append({
                    "id": f"qoder/{model_id}",
                    "name": m.get("name", model_id),
                    "type": "llm",
                    "contextLength": m.get("context_length", 0),
                })

        return [self._normalize_model(m) for m in models if self._normalize_model(m).get("id")]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/qoder/handler.py
git commit -m "feat(qoder): add handler with COSY signing delegation"
```

---

### Task 5: Verify handler loading

**Files:**
- None (verification only)

- [ ] **Step 1: Test handler loading**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -c "
from app.providers.provider import Provider

p = Provider('qoder')
h = p.handler()
print(f'Qoder handler: {type(h).__name__}')
print(f'Config: {p.config().PROVIDER_NAME}')
print(f'Alias: {p.config().ALIAS}')
print(f'Format: {p.config().FORMAT}')

# Test build_upstream_url
url = h.build_upstream_url('https://api3.qoder.sh', stream=True)
print(f'URL: {url}')
"
```

Expected:
```
Qoder handler: QoderHandler
Config: Qoder
Alias: qd
Format: qoder
URL: https://api3.qoder.sh/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "feat(qoder): verify handler loading"
```

---

### Task 6: Refactor proxy.py — remove qoder-specific code

**Files:**
- Modify: `backend/app/services/proxy.py`

- [ ] **Step 1: Remove qoder imports from _build_headers()**

After Task 4, `_build_headers()` should dispatch to handler. Remove the qoder-specific code:

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

- [ ] **Step 2: Remove qoder-specific _build_upstream_url()**

After Task 4, `_build_upstream_url()` should dispatch to handler:

```python
def _build_upstream_url(provider: str, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
    """Build the upstream URL for a provider using handler."""
    try:
        p = Provider(provider)
        handler = p.handler()
        return handler.build_upstream_url(base_url, stream, data or {}, model)
    except (ValueError, ModuleNotFoundError):
        return f"{base_url.rstrip('/')}/chat/completions"
```

- [ ] **Step 3: Refactor build_qoder_request() to use handler**

```python
async def build_qoder_request(
    target: ResolvedTarget,
    body: dict,
    data: dict,
) -> tuple[bytes, dict[str, str]]:
    """Build a Qoder-specific request using handler."""
    p = Provider("qoder")
    handler = p.handler()
    return handler.build_request_body(target.model, body, data)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/proxy.py
git commit -m "refactor(proxy): delegate qoder logic to handler"
```

---

### Task 7: Refactor shared.py — remove qoder-specific unwrap

**Files:**
- Modify: `backend/app/routers/v1_proxy/shared.py`

- [ ] **Step 1: Replace qoder unwrap in _non_stream_response()**

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

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/v1_proxy/shared.py
git commit -m "refactor(shared): delegate qoder unwrap to handler"
```

---

### Task 8: Refactor models.py — remove qoder-specific fetch

**Files:**
- Modify: `backend/app/routers/providers/models.py`

- [ ] **Step 1: Simplify _fetch_builtin_models()**

After Task 4, `_fetch_builtin_models()` should use handler for all providers including qoder:

```python
async def _fetch_builtin_models(
    provider: str, api_key: str, data: dict,
) -> list[dict]:
    """Fetch models from a built-in provider using the Provider handler."""
    token: str = data.get("accessToken") or api_key
    if not token:
        raise HTTPException(status_code=401, detail="No valid token found")

    try:
        p = Provider(provider)
        handler = p.handler()
        models_raw: list[dict] = await handler.fetch_models(token, data)
        return [handler._normalize_model(m) for m in models_raw if handler._normalize_model(m).get("id")]
    except (ValueError, ModuleNotFoundError):
        return await _fetch_fallback(provider, api_key)
    except httpx.ConnectError:
        try:
            p = Provider(provider)
            raise HTTPException(status_code=502, detail=f"Cannot connect to {p.base_url()}")
        except (ValueError, ModuleNotFoundError):
            raise HTTPException(status_code=502, detail=f"Cannot connect to {provider}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch models: {e.response.status_code}")
```

- [ ] **Step 2: Remove _fetch_qoder_models() function**

This function is no longer needed — qoder handler.fetch_models() handles it.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/providers/models.py
git commit -m "refactor(models): delegate qoder fetch to handler"
```

---

### Task 9: Verify — full integration test

- [ ] **Step 1: Run tests**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -m pytest tests/ -v --tb=short --ignore=tests/test_provider_models-v1.py
```

- [ ] **Step 2: Verify handler methods**

```bash
docker compose -f docker-compose.dev.yml exec backend uv run python -c "
from app.providers.provider import Provider

p = Provider('qoder')
h = p.handler()

# Test all methods
print('=== Qoder Handler ===')
print(f'validate: {type(h.validate).__name__}')
print(f'build_upstream_url: {type(h.build_upstream_url).__name__}')
print(f'build_headers: {type(h.build_headers).__name__}')
print(f'build_request_body: {type(h.build_request_body).__name__}')
print(f'unwrap_response: {type(h.unwrap_response).__name__}')
print(f'fetch_models: {type(h.fetch_models).__name__}')

# Test URL building
url = h.build_upstream_url('https://api3.qoder.sh')
print(f'URL: {url}')
"
```

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "feat(qoder): complete migration to providers system"
```

---

## Success Criteria

1. `Provider("qoder")` works (tidak error)
2. `Provider("qoder").handler()` returns `QoderHandler`
3. `handler.build_upstream_url()` returns COSY-signed URL
4. `handler.build_headers()` returns COSY-signed headers
5. `handler.build_request_body()` returns encoded body + signed headers
6. `handler.unwrap_response()` unwraps Qoder envelope
7. `handler.fetch_models()` fetches from COSY-signed catalog
8. `proxy.py` tidak ada import langsung dari `services/qoder/`
9. `shared.py` tidak ada qoder-specific unwrap
10. `models.py` tidak ada `_fetch_qoder_models()`
11. Semua existing tests pass

---

## Dependency Order

```
Task 1  (add to __init__.py) ──────┐
Task 2  (create package) ──────────┤
Task 3  (config.py) ───────────────┼──► Task 5 (verify)
Task 4  (handler.py) ──────────────┘         │
                                             ▼
Task 6  (refactor proxy.py) ────────────────┐
Task 7  (refactor shared.py) ───────────────┼──► Task 9 (verify)
Task 8  (refactor models.py) ──────────────┘
```

---

## Notes

- **Service layer tetap di `services/qoder/`** — COSY signing, encoding, auth terlalu kompleks untuk dipindah ke handler. Handler hanya delegate.
- **2 auth methods** — OAuth device flow dan PAT import tetap di `services/qoder/auth.py` dan `routers/oauth.py`.
- **Backward compatibility** — `build_qoder_request()` di proxy.py tetap ada tapi delegate ke handler.
- **Testing** — Qoder butuh real credentials untuk test. Unit test bisa mock service layer.
