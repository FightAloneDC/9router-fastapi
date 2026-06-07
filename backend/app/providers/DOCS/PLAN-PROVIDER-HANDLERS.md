# Provider Handlers — Pindahkan Logic Provider-Specific ke Provider Module

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pindahkan semua fungsi provider-specific (validation, testing, model fetching) dari `backend/app/routers/providers/` ke masing-masing `backend/app/providers/<provider>/handler.py`. Router hanya dispatch, bukan contain logic.

**Architecture:** Tambah base class `BaseProviderHandler` di `providers/base.py`. Setiap provider punya `handler.py` yang implement `validate()`, `test_connection()`, `fetch_models()`. Router dispatch ke `Provider(provider).handler().validate(...)` menggantikan if/elif chain.

**Tech Stack:** Python, FastAPI, httpx, Pydantic

---

## Problem

File-file di `backend/app/routers/providers/` mengandung logic provider-specific:

| File | Problem |
|------|---------|
| `validation.py` (390 baris) | 15 fungsi `_validate_*()` — satu per provider type |
| `testing.py` (340 baris) | `_test_provider_connection()` punya if/elif chain panjang |
| `models.py` (304 baris) | `_fetch_builtin_models()`, `_fetch_fallback()`, `_fetch_qoder_models()` |
| `helpers.py` (220 baris) | `_get_base_url()` punya special case `xiaomi-tokenplan` |
| `connections.py` (450 baris) | `create_provider()` punya validation khusus untuk `azure` dan `cloudflare-ai` |

**Akibat:**
- Tambah provider baru = edit 4-5 file di routers
- Provider-specific code bercampur dengan generic routing logic
- Sulit test individual provider

**Solusi:** Setiap provider punya `handler.py` yang handle semua provider-specific logic. Router tinggal dispatch.

---

## Current State → Target State

### Current (if/elif chain di router):

```python
# testing.py — _test_provider_connection()
vtype = _get_validation_type(provider)

if vtype == "anthropic":
    result = await _validate_anthropic(api_key, base_url)
    return {...}
if vtype == "google":
    result = await _validate_google(api_key)
    return {...}
if vtype == "azure":
    result = await _validate_azure(api_key, data)
    return {...}
# ... 12 more elif
```

### Target (dispatch ke handler):

```python
# testing.py — _test_provider_connection()
p = Provider(provider)
handler = p.handler()
result = await handler.validate(api_key, data)
return {"valid": result.valid, "error": result.error, ...}
```

---

## File Structure

### New Files

| File | Purpose |
|------|---------|
| `backend/app/providers/base.py` | Add `BaseProviderHandler` class |
| `backend/app/providers/openai/handler.py` | OpenAI validate + test + fetch |
| `backend/app/providers/anthropic/handler.py` | Anthropic validate + test + fetch |
| `backend/app/providers/gemini/handler.py` | Gemini validate + test + fetch |
| `backend/app/providers/azure/handler.py` | Azure validate + test + fetch |
| `backend/app/providers/cloudflare_ai/handler.py` | Cloudflare validate + test |
| `backend/app/providers/ollama/handler.py` | Ollama validate + test + fetch |
| `backend/app/providers/ollama_local/handler.py` | Ollama Local validate + test |
| `backend/app/providers/vertex/handler.py` | Vertex validate + test |
| `backend/app/providers/elevenlabs/handler.py` | ElevenLabs validate |
| `backend/app/providers/deepgram/handler.py` | Deepgram validate |
| `backend/app/providers/inworld/handler.py` | Inworld validate |
| `backend/app/providers/voyage_ai/handler.py` | Voyage AI validate |
| `backend/app/providers/assemblyai/handler.py` | AssemblyAI validate |
| `backend/app/providers/minimax/handler.py` | Minimax validate |
| `backend/app/providers/minimax_cn/handler.py` | Minimax CN validate |
| `backend/app/providers/kilo_gateway/handler.py` | Kilo Gateway validate |
| `backend/app/providers/edge_tts/handler.py` | Edge TTS (noauth) |
| `backend/app/providers/local_device/handler.py` | Local Device (noauth) |
| `backend/app/providers/xiaomi_tokenplan/handler.py` | Xiaomi region-aware base URL |
| `backend/app/providers/openrouter/handler.py` | OpenRouter extra headers |
| `backend/app/providers/openai_compatible/handler.py` | Generic fallback handler |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/providers/base.py` | Add `BaseProviderHandler` + `ValidateResult` |
| `backend/app/providers/provider.py` | Add `handler()` method |
| `backend/app/routers/providers/validation.py` | Replace 15 functions with dispatch |
| `backend/app/routers/providers/testing.py` | Replace if/elif chain with dispatch |
| `backend/app/routers/providers/models.py` | Replace `_fetch_builtin_models()` with dispatch |
| `backend/app/routers/providers/helpers.py` | Move `_get_base_url()` special cases to handlers |
| `backend/app/routers/providers/connections.py` | Replace provider-specific validation with dispatch |

---

## ValidateResult Schema

Semua handler return type yang sama:

```python
from dataclasses import dataclass, field

@dataclass
class ValidateResult:
    valid: bool
    error: str | None = None
    models: list[str] | None = None
    latency_ms: int = 0
```

---

## Provider-to-Handler Mapping

### Group 1: OpenAI-Compatible (default handler)

Provider yang pakai `Authorization: Bearer <key>` + `GET /models` standar:

```
openai, deepseek, groq, xai, mistral, perplexity, together, fireworks,
cerebras, cohere, nebius, siliconflow, hyperbolic, nvidia, opencode-go,
askcodi, vercel-ai-gateway, alicode, alicode-intl, volcengine-ark,
byteplus, volcengine, glm, glm-cn, kimi, minimax, minimax-cn,
xiaomi-mimo, xiaomi-tokenplan, nanobanana, huggingface,
tavily, brave-search, serper, exa, fal-ai, stability-ai, jina-ai,
blackbox, commandcode, recraft, replicate, runwayml, topaz,
sdwebui, comfyui, bfl, cartesia, playht, google-tts, coqui,
tortoise, firecrawl, crawl4ai, jina-reader, searchapi, searxng,
linkup, you-com, google-pse
```

→ Pakai `BaseProviderHandler` default (openai-compatible)

### Group 2: Custom Handler (provider-specific)

| Provider | Validation Type | Handler Needed |
|----------|----------------|----------------|
| anthropic | `anthropic` | Ya — x-api-key header + anthropic-version |
| gemini | `google` | Ya — query param auth |
| azure | `azure` | Ya — api-key header + deployment URL |
| cloudflare-ai | `cloudflare` | Ya — accountId + chat completion test |
| ollama | ollama | Ya — `/api/tags` endpoint |
| ollama-local | ollama | Ya — `/api/tags` endpoint |
| vertex | `vertex` | Ya — service account JSON parse |
| elevenlabs | `elevenlabs` | Ya — xi-api-key + `/voices` endpoint |
| deepgram | `deepgram` | Ya — Token prefix + custom model list |
| inworld | `inworld` | Ya — Basic auth + `/voices` endpoint |
| voyage-ai | `voyage` | Ya — embedding test call |
| assemblyai | `assemblyai` | Ya — raw API key + transcript endpoint |
| minimax | `minimax` | Ya — `/get_voice` endpoint |
| minimax-cn | `minimax-cn` | Ya — CN endpoint variant |
| kilo-gateway | `openai-chat` | Ya — custom error parsing |
| edge-tts | `noauth` | Ya — always valid |
| local-device | `noauth` | Ya — always valid |

---

## Tasks

### Task 1: Add BaseProviderHandler dan ValidateResult ke base.py

**Files:**
- Modify: `backend/app/providers/base.py`

- [ ] **Step 1: Tambah BaseProviderHandler dan ValidateResult**

Tambah setelah `BaseMetadata` class:

```python
from dataclasses import dataclass, field

@dataclass
class ValidateResult:
    """Standardized result from provider validation."""
    valid: bool
    error: str | None = None
    models: list[str] | None = None
    latency_ms: int = 0


class BaseProviderHandler:
    """Base handler for provider-specific operations.

    Override methods in child class for provider-specific behavior.
    Default implementation uses OpenAI-compatible API.
    """

    def __init__(self, config: "BaseProviderConfig") -> None:
        self.config = config

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        """Validate provider credentials.

        Args:
            api_key: Provider API key or token
            data: Connection data dict (providerSpecificData, baseUrl, etc.)

        Returns:
            ValidateResult with valid, error, models
        """
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")
        base_url = self._resolve_base_url(data)
        if not base_url:
            return ValidateResult(valid=False, error="Base URL is required")
        return await self._validate_openai_compatible(api_key, base_url, data)

    async def test_connection(self, api_key: str, data: dict | None = None) -> ValidateResult:
        """Test provider connection. Same as validate by default."""
        return await self.validate(api_key, data)

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        """Fetch available models from provider.

        Returns:
            List of model dicts with at least {id, name, type}
        """
        from app.providers.model_helpers import fetch_models_header_auth

        if not api_key:
            raise ValueError("No API key configured")

        config = self._build_fetch_config(data)
        models_raw = await fetch_models_header_auth(config, api_key)
        return [self._normalize_model(m) for m in models_raw if self._normalize_model(m).get("id")]

    def resolve_base_url(self, data: dict | None = None) -> str:
        """Resolve effective base URL from config + connection data."""
        return self._resolve_base_url(data)

    def _resolve_base_url(self, data: dict | None = None) -> str:
        """Internal: resolve base URL."""
        if data and data.get("baseUrl"):
            return data["baseUrl"].rstrip("/")
        return self.config.BASE_URL.rstrip("/") if self.config.BASE_URL else ""

    def _build_fetch_config(self, data: dict | None = None) -> "BaseProviderConfig":
        """Build config for model fetching."""
        from app.providers.base import BaseProviderConfig as BPC
        return BPC(
            PROVIDER_NAME=self.config.PROVIDER_NAME,
            PROVIDER_ID=self.config.PROVIDER_ID,
            ALIAS=self.config.ALIAS,
            BASE_URL=self._resolve_base_url(data),
            AUTH_HEADER=self.config.AUTH_HEADER,
            AUTH_PREFIX=self.config.AUTH_PREFIX,
            EXTRA_HEADERS=self.config.EXTRA_HEADERS,
        )

    async def _validate_openai_compatible(
        self, api_key: str, base_url: str, data: dict | None = None
    ) -> ValidateResult:
        """Default validation: GET /models with Bearer auth."""
        import time
        import httpx

        start = time.monotonic()
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        if self.config.EXTRA_HEADERS:
            headers.update(self.config.EXTRA_HEADERS)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 401:
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code == 403:
                    return ValidateResult(valid=False, error="API key forbidden", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"HTTP {resp.status_code}", latency_ms=latency)
                data_resp = resp.json()
                models = []
                if isinstance(data_resp, dict) and "data" in data_resp:
                    models = [m.get("id", "") for m in data_resp["data"] if m.get("id")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error=f"Cannot connect to {base_url}", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    def _normalize_model(self, m) -> dict:
        """Normalize a model entry to {id, name, type}."""
        from app.routers.providers.constants import infer_model_type, _get_model_type_overrides

        if isinstance(m, str):
            return {"id": m, "name": m, "type": infer_model_type(m)}
        model_id = m.get("id") or m.get("name") or m.get("model", "")
        name = m.get("name") or m.get("display_name") or m.get("displayName") or m.get("id", "")
        model_type = m.get("type") or _get_model_type_overrides().get(model_id) or infer_model_type(model_id)
        return {"id": model_id, "name": name, "type": model_type}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/base.py
git commit -m "feat(providers): add BaseProviderHandler and ValidateResult"
```

---

### Task 2: Tambah handler() method ke Provider class

**Files:**
- Modify: `backend/app/providers/provider.py`

- [ ] **Step 1: Tambah handler() method**

Tambah import dan method baru:

```python
import importlib
from typing import TYPE_CHECKING

from app.providers.base import BaseMetadata, BaseProviderConfig, BaseProviderHandler

if TYPE_CHECKING:
    from app.providers.base import BaseProviderHandler


class Provider:
    """Unified accessor for provider config and models."""

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._module_name: str = name.replace("-", "_")
        self._config: BaseProviderConfig | None = None
        self._metadata: BaseMetadata | None = None
        self._models = None
        self._handler: BaseProviderHandler | None = None

    # ... existing methods stay the same ...

    def handler(self) -> "BaseProviderHandler":
        """Return the provider's handler instance.

        Tries to load provider-specific handler class first.
        Falls back to BaseProviderHandler with provider config.
        """
        if self._handler is None:
            try:
                module = importlib.import_module(
                    f"app.providers.{self._module_name}.handler"
                )
                for attr in dir(module):
                    cls = getattr(module, attr)
                    if (
                        isinstance(cls, type)
                        and issubclass(cls, BaseProviderHandler)
                        and cls is not BaseProviderHandler
                    ):
                        self._handler = cls(self.config())
                        return self._handler
            except (ModuleNotFoundError, ImportError):
                pass
            # Fallback: base handler with provider config
            self._handler = BaseProviderHandler(self.config())
        return self._handler
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/provider.py
git commit -m "feat(providers): add handler() method to Provider class"
```

---

### Task 3: Buat Anthropic handler

**Files:**
- Create: `backend/app/providers/anthropic/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Anthropic provider handler — x-api-key auth + custom validation."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class AnthropicHandler(BaseProviderHandler):
    """Handler for Anthropic provider (x-api-key auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        base_url = self._resolve_base_url(data)
        if base_url:
            url = base_url.rstrip("/")
            if url.endswith("/messages"):
                url = url[:-9]
            url = f"{url}/models"
        else:
            url = "https://api.anthropic.com/v1/models"

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 500:
                    return ValidateResult(valid=False, error=f"Server error ({resp.status_code})", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to provider", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        from app.providers.model_helpers import fetch_models_header_auth
        from app.providers.base import BaseProviderConfig

        if not api_key:
            raise ValueError("No API key configured")

        base_url = self._resolve_base_url(data)
        config = BaseProviderConfig(
            PROVIDER_NAME="Anthropic",
            PROVIDER_ID="anthropic",
            ALIAS="an",
            BASE_URL=base_url or "https://api.anthropic.com/v1",
            AUTH_HEADER="x-api-key",
            AUTH_PREFIX="",
            EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
        )
        models_raw = await fetch_models_header_auth(config, api_key)
        return [self._normalize_model(m) for m in models_raw if self._normalize_model(m).get("id")]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/anthropic/handler.py
git commit -m "feat(anthropic): add provider handler"
```

---

### Task 4: Buat Gemini handler

**Files:**
- Create: `backend/app/providers/gemini/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Gemini provider handler — query param auth (?key=)."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class GeminiHandler(BaseProviderHandler):
    """Handler for Gemini/Google provider (query param auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        start = time.monotonic()
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Google returned {resp.status_code}", latency_ms=latency)
                data_resp = resp.json()
                models = []
                if isinstance(data_resp, dict) and "models" in data_resp:
                    models = [m.get("name", "").replace("models/", "") for m in data_resp["models"] if m.get("name")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Google API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        from app.providers.model_helpers import fetch_models_query_auth
        from app.providers.base import BaseProviderConfig

        if not api_key:
            raise ValueError("No API key configured")

        config = BaseProviderConfig(
            PROVIDER_NAME="Gemini",
            PROVIDER_ID="gemini",
            ALIAS="gemini",
            BASE_URL="https://generativelanguage.googleapis.com/v1beta",
            AUTH_QUERY_PARAM="key",
        )
        models_raw = await fetch_models_query_auth(config, api_key)

        # Gemini returns models differently
        normalized = []
        for m in models_raw:
            name = m.get("name", "").replace("models/", "")
            if name:
                normalized.append({"id": name, "name": name})
        return [self._normalize_model(m) for m in normalized if self._normalize_model(m).get("id")]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/gemini/handler.py
git commit -m "feat(gemini): add provider handler"
```

---

### Task 5: Buat Azure handler

**Files:**
- Create: `backend/app/providers/azure/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Azure OpenAI provider handler — api-key header + deployment URL."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class AzureHandler(BaseProviderHandler):
    """Handler for Azure OpenAI provider."""

    def _resolve_base_url(self, data: dict | None = None) -> str:
        """Azure uses azureEndpoint from providerSpecificData."""
        if data:
            endpoint = data.get("azureEndpoint") or data.get("endpoint") or ""
            if endpoint:
                return endpoint.rstrip("/")
        return super()._resolve_base_url(data)

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        data = data or {}
        endpoint = (data.get("azureEndpoint") or data.get("endpoint") or "").rstrip("/")
        deployment = data.get("deployment") or ""
        api_version = data.get("apiVersion") or "2024-02-15-preview"

        if not endpoint:
            return ValidateResult(valid=False, error="Azure endpoint URL is required")
        if not deployment:
            return ValidateResult(valid=False, error="Azure deployment name is required")

        start = time.monotonic()
        url = f"{endpoint}/openai/deployments?api-version={api_version}"
        headers = {"api-key": api_key}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Azure returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error=f"Cannot connect to {endpoint}", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/azure/handler.py
git commit -m "feat(azure): add provider handler"
```

---

### Task 6: Buat Cloudflare AI handler

**Files:**
- Create: `backend/app/providers/cloudflare_ai/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Cloudflare AI handler — accountId + chat completion test."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class CloudflareAiHandler(BaseProviderHandler):
    """Handler for Cloudflare AI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        data = data or {}
        account_id = data.get("accountId", "")
        if not account_id:
            return ValidateResult(valid=False, error="Cloudflare Account ID is required")
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Cloudflare AI")

        start = time.monotonic()
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "@cf/meta/llama-3-8b-instruct",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key or Account ID (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    resp_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    errors = resp_data.get("errors", [])
                    msg = errors[0].get("message", f"Cloudflare returned {resp.status_code}") if errors else f"Cloudflare returned {resp.status_code}"
                    return ValidateResult(valid=False, error=msg, latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Cloudflare API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/cloudflare_ai/handler.py
git commit -m "feat(cloudflare-ai): add provider handler"
```

---

### Task 7: Buat Ollama handler

**Files:**
- Create: `backend/app/providers/ollama/handler.py`
- Create: `backend/app/providers/ollama_local/handler.py`

- [ ] **Step 1: Buat ollama/handler.py**

```python
"""Ollama handler — /api/tags endpoint, no auth."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class OllamaHandler(BaseProviderHandler):
    """Handler for Ollama provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        base_url = self._resolve_base_url(data) or "http://localhost:11434"

        start = time.monotonic()
        url = f"{base_url}/api/tags"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(url)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Ollama returned {resp.status_code}", latency_ms=latency)
                data_resp = resp.json()
                models = [m.get("name", "") for m in data_resp.get("models", []) if m.get("name")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error=f"Cannot connect to Ollama at {base_url}. Is it running?", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        base_url = self._resolve_base_url(data) or "http://localhost:11434"
        url = f"{base_url}/api/tags"

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data_resp = resp.json()
            models = []
            for m in data_resp.get("models", []):
                name = m.get("name", "")
                if name:
                    models.append({"id": name, "name": name})
            return [self._normalize_model(m) for m in models if self._normalize_model(m).get("id")]
```

- [ ] **Step 2: Buat ollama_local/handler.py**

```python
"""Ollama Local handler — same as Ollama but for local device."""

from app.providers.ollama.handler import OllamaHandler


class OllamaLocalHandler(OllamaHandler):
    """Handler for Ollama Local provider (same behavior as Ollama)."""
    pass
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/ollama/handler.py backend/app/providers/ollama_local/handler.py
git commit -m "feat(ollama): add provider handlers"
```

---

### Task 8: Buat Vertex handler

**Files:**
- Create: `backend/app/providers/vertex/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Vertex AI handler — service account JSON + API key validation."""

import json
import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class VertexHandler(BaseProviderHandler):
    """Handler for Vertex AI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key or service account JSON is required")

        # Service account JSON
        try:
            parsed = json.loads(api_key)
            if isinstance(parsed, dict) and parsed.get("type") == "service_account":
                valid = bool(parsed.get("client_email") and parsed.get("private_key") and parsed.get("project_id"))
                return ValidateResult(valid=valid, error=None if valid else "Invalid service account JSON")
        except (json.JSONDecodeError, TypeError):
            pass

        # Raw API key: probe Vertex
        start = time.monotonic()
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/__probe__:generateContent?key={api_key}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers={"Content-Type": "application/json"}, json={})
                latency = int((time.monotonic() - start) * 1000)
                valid = resp.status_code not in (401, 403)
                return ValidateResult(valid=valid, error=None if valid else "Invalid API key", latency_ms=latency)
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/vertex/handler.py
git commit -m "feat(vertex): add provider handler"
```

---

### Task 9: Buat ElevenLabs handler

**Files:**
- Create: `backend/app/providers/elevenlabs/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""ElevenLabs handler — xi-api-key auth + /voices endpoint."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class ElevenlabsHandler(BaseProviderHandler):
    """Handler for ElevenLabs provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for ElevenLabs")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": api_key},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"ElevenLabs returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                voices = resp.json().get("voices", [])
                models = [v.get("voice_id", "") for v in voices if v.get("voice_id")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to ElevenLabs API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/elevenlabs/handler.py
git commit -m "feat(elevenlabs): add provider handler"
```

---

### Task 10: Buat Deepgram handler

**Files:**
- Create: `backend/app/providers/deepgram/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Deepgram handler — Token auth + custom model list."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class DeepgramHandler(BaseProviderHandler):
    """Handler for Deepgram provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Deepgram")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://api.deepgram.com/v1/models",
                    headers={"Authorization": f"Token {api_key}"},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Deepgram returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                data_resp = resp.json()
                tts_models = [m.get("canonical_name") or m.get("name", "") for m in data_resp.get("tts", []) if m.get("name")]
                stt_models = [m.get("canonical_name") or m.get("name", "") for m in data_resp.get("stt", []) if m.get("name")]
                all_models = tts_models + stt_models
                return ValidateResult(valid=True, models=all_models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Deepgram API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/deepgram/handler.py
git commit -m "feat(deepgram): add provider handler"
```

---

### Task 11: Buat Inworld handler

**Files:**
- Create: `backend/app/providers/inworld/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Inworld handler — Basic auth + /voices endpoint."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class InworldHandler(BaseProviderHandler):
    """Handler for Inworld provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Inworld")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://api.inworld.ai/tts/v1/voices",
                    headers={"Authorization": f"Basic {api_key}"},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Inworld returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                voices = resp.json().get("voices", [])
                models = [v.get("voiceId", "") for v in voices if v.get("voiceId")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Inworld API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/inworld/handler.py
git commit -m "feat(inworld): add provider handler"
```

---

### Task 12: Buat Voyage AI handler

**Files:**
- Create: `backend/app/providers/voyage_ai/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Voyage AI handler — embedding test call for validation."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class VoyageAiHandler(BaseProviderHandler):
    """Handler for Voyage AI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Voyage AI")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"input": "ping", "model": "voyage-3"},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 500:
                    return ValidateResult(valid=False, error=f"Voyage returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Voyage AI API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/voyage_ai/handler.py
git commit -m "feat(voyage-ai): add provider handler"
```

---

### Task 13: Buat AssemblyAI handler

**Files:**
- Create: `backend/app/providers/assemblyai/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""AssemblyAI handler — raw API key + transcript endpoint."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class AssemblyaiHandler(BaseProviderHandler):
    """Handler for AssemblyAI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for AssemblyAI")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://api.assemblyai.com/v2/transcript?limit=1",
                    headers={"Authorization": api_key},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"AssemblyAI returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to AssemblyAI API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/assemblyai/handler.py
git commit -m "feat(assemblyai): add provider handler"
```

---

### Task 14: Buat Minimax handlers

**Files:**
- Create: `backend/app/providers/minimax/handler.py`
- Create: `backend/app/providers/minimax_cn/handler.py`

- [ ] **Step 1: Buat minimax/handler.py**

```python
"""Minimax handler — /get_voice endpoint."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class MinimaxHandler(BaseProviderHandler):
    """Handler for Minimax provider."""

    ENDPOINT = "https://api.minimax.io/v1/get_voice"

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for MiniMax")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    self.ENDPOINT,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"voice_type": "all"},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"MiniMax returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                resp_data = resp.json()
                base_resp = resp_data.get("base_resp") or resp_data.get("baseResp", {})
                status_code = base_resp.get("status_code") or base_resp.get("statusCode", 0)
                if status_code != 0:
                    return ValidateResult(valid=False, error=base_resp.get("status_msg") or base_resp.get("statusMsg", "MiniMax error"), latency_ms=latency)
                voices = resp_data.get("system_voice", []) or []
                voice_ids = [v.get("voice_id") or v.get("voiceId", "") for v in voices if v.get("voice_id") or v.get("voiceId")]
                return ValidateResult(valid=True, models=voice_ids or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to MiniMax API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Buat minimax_cn/handler.py**

```python
"""Minimax CN handler — same as Minimax but CN endpoint."""

from app.providers.minimax.handler import MinimaxHandler


class MinimaxCnHandler(MinimaxHandler):
    """Handler for Minimax CN provider."""

    ENDPOINT = "https://api.minimaxi.com/v1/get_voice"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/minimax/handler.py backend/app/providers/minimax_cn/handler.py
git commit -m "feat(minimax): add provider handlers"
```

---

### Task 15: Buat Kilo Gateway handler

**Files:**
- Create: `backend/app/providers/kilo_gateway/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Kilo Gateway handler — openai-chat validation type with custom error parsing."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class KiloGatewayHandler(BaseProviderHandler):
    """Handler for Kilo Gateway provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Kilo Gateway")

        base_url = self._resolve_base_url(data)
        if not base_url:
            return ValidateResult(valid=False, error="Base URL is required")

        start = time.monotonic()
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    resp_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    error_msg = resp_data.get("error", {}).get("message", f"Kilo Gateway returned {resp.status_code}") if isinstance(resp_data.get("error"), dict) else f"Kilo Gateway returned {resp.status_code}"
                    return ValidateResult(valid=False, error=error_msg, latency_ms=latency)
                data_resp = resp.json()
                models = [m.get("id") for m in data_resp.get("data", []) if isinstance(m, dict)]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Kilo Gateway API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/kilo_gateway/handler.py
git commit -m "feat(kilo-gateway): add provider handler"
```

---

### Task 16: Buat NoAuth handlers (edge-tts, local-device)

**Files:**
- Create: `backend/app/providers/edge_tts/handler.py`
- Create: `backend/app/providers/local_device/handler.py`

- [ ] **Step 1: Buat edge_tts/handler.py**

```python
"""Edge TTS handler — no authentication required."""

from app.providers.base import BaseProviderHandler, ValidateResult


class EdgeTtsHandler(BaseProviderHandler):
    """Handler for Edge TTS provider (no auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        return ValidateResult(valid=True, models=None)
```

- [ ] **Step 2: Buat local_device/handler.py**

```python
"""Local Device handler — no authentication required."""

from app.providers.base import BaseProviderHandler, ValidateResult


class LocalDeviceHandler(BaseProviderHandler):
    """Handler for Local Device provider (no auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        return ValidateResult(valid=True, models=None)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/edge_tts/handler.py backend/app/providers/local_device/handler.py
git commit -m "feat(noauth): add edge-tts and local-device handlers"
```

---

### Task 17: Buat Xiaomi TokenPlan handler

**Files:**
- Create: `backend/app/providers/xiaomi_tokenplan/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""Xiaomi TokenPlan handler — region-aware base URL resolution."""

from app.providers.base import BaseProviderHandler


class XiaomiTokenplanHandler(BaseProviderHandler):
    """Handler for Xiaomi TokenPlan provider (region-aware)."""

    REGION_URLS = {
        "sgp": "https://token-plan-sgp.xiaomimimo.com/v1",
        "cn": "https://token-plan-cn.xiaomimimo.com/v1",
        "ams": "https://token-plan-ams.xiaomimimo.com/v1",
    }

    def _resolve_base_url(self, data: dict | None = None) -> str:
        if data:
            region = data.get("region", "sgp")
            if region in self.REGION_URLS:
                return self.REGION_URLS[region].rstrip("/")
            if data.get("baseUrl"):
                return data["baseUrl"].rstrip("/")
        return super()._resolve_base_url(data)

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        from app.providers.model_helpers import fetch_models_header_auth
        from app.providers.base import BaseProviderConfig

        if not api_key:
            raise ValueError("No API key configured")

        base_url = self._resolve_base_url(data)
        config = BaseProviderConfig(
            PROVIDER_NAME="Xiaomi TokenPlan",
            PROVIDER_ID="xiaomi-tokenplan",
            ALIAS="xmtp",
            BASE_URL=base_url,
            AUTH_HEADER=self.config.AUTH_HEADER,
            AUTH_PREFIX=self.config.AUTH_PREFIX,
        )
        models_raw = await fetch_models_header_auth(config, api_key)
        return [self._normalize_model(m) for m in models_raw if self._normalize_model(m).get("id")]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/xiaomi_tokenplan/handler.py
git commit -m "feat(xiaomi-tokenplan): add region-aware handler"
```

---

### Task 18: Buat OpenRouter handler

**Files:**
- Create: `backend/app/providers/openrouter/handler.py`

- [ ] **Step 1: Buat handler.py**

```python
"""OpenRouter handler — extra headers (HTTP-Referer, X-Title)."""

from app.providers.base import BaseProviderHandler, ValidateResult


class OpenrouterHandler(BaseProviderHandler):
    """Handler for OpenRouter provider (extra headers support)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        base_url = self._resolve_base_url(data) or "https://openrouter.ai/api/v1"

        # Build extra headers from connection data
        extra_headers = {}
        if data:
            if data.get("httpReferer"):
                extra_headers["HTTP-Referer"] = data["httpReferer"]
            if data.get("xTitle"):
                extra_headers["X-Title"] = data["xTitle"]

        # Temporarily inject extra headers for validation
        original = self.config.EXTRA_HEADERS
        self.config = type(self.config)(
            **{**self.config.model_dump(), "EXTRA_HEADERS": {**self.config.EXTRA_HEADERS, **extra_headers}}
        )
        try:
            result = await self._validate_openai_compatible(api_key, base_url, data)
        finally:
            self.config = type(self.config)(
                **{**self.config.model_dump(), "EXTRA_HEADERS": original}
            )
        return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/providers/openrouter/handler.py
git commit -m "feat(openrouter): add provider handler with extra headers"
```

---

### Task 19: Refactor validation.py — dispatch ke handler

**Files:**
- Modify: `backend/app/routers/providers/validation.py`

- [ ] **Step 1: Replace all _validate_* functions with dispatch**

Tulis ulang `validation.py`:

```python
"""Provider credential validation — dispatches to provider handlers."""

from app.providers.provider import Provider
from app.providers.base import ValidateResult
from app.schemas.provider import ProviderValidateResponse


async def _validate_provider(provider: str, api_key: str, data: dict | None = None) -> ProviderValidateResponse:
    """Validate provider credentials using provider handler.

    Dispatches to the appropriate provider handler based on provider ID.
    """
    try:
        p = Provider(provider)
        handler = p.handler()
        result = await handler.validate(api_key, data)
        return ProviderValidateResponse(
            valid=result.valid,
            error=result.error,
            models=result.models,
        )
    except (ValueError, ModuleNotFoundError):
        # Fallback for unknown providers
        return ProviderValidateResponse(
            valid=False,
            error=f"Unknown provider: {provider}",
        )


async def _validate_openai_compatible(
    api_key: str, base_url: str, extra_headers: dict | None = None
) -> ProviderValidateResponse:
    """Legacy wrapper — validates an OpenAI-compatible endpoint directly.

    Used for custom nodes and fallback cases where no provider handler exists.
    """
    from app.providers.base import BaseProviderConfig, BaseProviderHandler

    config = BaseProviderConfig(
        PROVIDER_NAME="custom",
        PROVIDER_ID="custom",
        ALIAS="custom",
        BASE_URL=base_url,
        EXTRA_HEADERS=extra_headers or {},
    )
    handler = BaseProviderHandler(config)
    result = await handler.validate(api_key)
    return ProviderValidateResponse(
        valid=result.valid,
        error=result.error,
        models=result.models,
    )


# Keep individual functions as thin wrappers for backward compatibility
# during migration. These will be removed once all callers are updated.

async def _validate_anthropic(api_key: str, base_url: str | None = None) -> ProviderValidateResponse:
    data = {"baseUrl": base_url} if base_url else {}
    return await _validate_provider("anthropic", api_key, data)


async def _validate_google(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("gemini", api_key)


async def _validate_azure(api_key: str, extra_data: dict) -> ProviderValidateResponse:
    return await _validate_provider("azure", api_key, extra_data)


async def _validate_cloudflare(api_key: str, extra_data: dict) -> ProviderValidateResponse:
    return await _validate_provider("cloudflare-ai", api_key, extra_data)


async def _validate_openai_chat(api_key: str, base_url: str) -> ProviderValidateResponse:
    return await _validate_provider("kilo-gateway", api_key, {"baseUrl": base_url})


async def _validate_ollama(base_url: str) -> ProviderValidateResponse:
    return await _validate_provider("ollama", api_key="", data={"baseUrl": base_url})


async def _validate_vertex(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("vertex", api_key)


async def _validate_noauth() -> ProviderValidateResponse:
    return await _validate_provider("edge-tts", api_key="")


async def _validate_elevenlabs(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("elevenlabs", api_key)


async def _validate_deepgram(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("deepgram", api_key)


async def _validate_inworld(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("inworld", api_key)


async def _validate_voyage(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("voyage-ai", api_key)


async def _validate_assemblyai(api_key: str) -> ProviderValidateResponse:
    return await _validate_provider("assemblyai", api_key)


async def _validate_minimax(api_key: str, region: str = "minimax") -> ProviderValidateResponse:
    provider = "minimax-cn" if region == "minimax-cn" else "minimax"
    return await _validate_provider(provider, api_key)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/providers/validation.py
git commit -m "refactor(validation): dispatch to provider handlers"
```

---

### Task 20: Refactor testing.py — dispatch ke handler

**Files:**
- Modify: `backend/app/routers/providers/testing.py`

- [ ] **Step 1: Simplify _test_provider_connection()**

Replace the entire `_test_provider_connection()` function:

```python
async def _test_provider_connection(conn: ProviderConnection, db: AsyncSession) -> dict:
    """Test a single provider connection using provider handler."""
    import time

    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key = data.get("apiKey", "") or data.get("accessToken", "")
    provider = conn.provider

    # Check if this is a compatible provider (node-based)
    node_result = await db.execute(
        select(ProviderNode).where(ProviderNode.id == provider)
    )
    node = node_result.scalar_one_or_none()

    if node:
        node_data = {}
        try:
            node_data = json.loads(node.data) if node.data else {}
        except (json.JSONDecodeError, TypeError):
            pass
        node_base_url = node_data.get("baseUrl", "")
        node_type = node.type

        # Use handler for node-based providers
        from app.providers.base import BaseProviderConfig, BaseProviderHandler

        if node_type == "anthropic-compatible":
            config = BaseProviderConfig(
                PROVIDER_NAME=node.name or node.id,
                PROVIDER_ID=node.id,
                ALIAS=node.id,
                BASE_URL=node_base_url,
                AUTH_HEADER="x-api-key",
                AUTH_PREFIX="",
                EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
            )
        else:
            config = BaseProviderConfig(
                PROVIDER_NAME=node.name or node.id,
                PROVIDER_ID=node.id,
                ALIAS=node.id,
                BASE_URL=node_base_url,
            )
        handler = BaseProviderHandler(config)
        result = await handler.validate(api_key, data)
        return {"valid": result.valid, "error": result.error, "latencyMs": result.latency_ms, "models": result.models}

    # Built-in provider — use handler
    if not api_key:
        return {"valid": False, "error": "No API key configured for this connection", "latencyMs": 0, "models": None}

    try:
        p = Provider(provider)
        handler = p.handler()
        result = await handler.validate(api_key, data)
        return {"valid": result.valid, "error": result.error, "latencyMs": result.latency_ms, "models": result.models}
    except (ValueError, ModuleNotFoundError):
        # Fallback for unknown providers
        from app.providers.base import BaseProviderConfig, BaseProviderHandler
        defaults = _get_provider_config(provider)
        default_url = defaults.get("baseUrl", "")
        if default_url:
            config = BaseProviderConfig(
                PROVIDER_NAME=provider,
                PROVIDER_ID=provider,
                ALIAS=provider,
                BASE_URL=default_url,
            )
            handler = BaseProviderHandler(config)
            result = await handler.validate(api_key, data)
            return {"valid": result.valid, "error": result.error, "latencyMs": result.latency_ms, "models": result.models}
        return {"valid": False, "error": f"Provider {provider} does not support connection testing", "latencyMs": 0, "models": None}
```

Also simplify `validate_provider()` endpoint:

```python
@router.post("/providers/validate", response_model=ProviderValidateResponse)
async def validate_provider(
    body: ProviderValidateRequest,
    _user=Depends(get_current_user),
):
    """Validate provider credentials using provider handler."""
    from app.routers.providers.validation import _validate_provider, _validate_openai_compatible

    extra = body.providerSpecificData or {}

    # Special handling for OpenRouter extra headers
    extra_headers = {}
    if extra.get("httpReferer"):
        extra_headers["HTTP-Referer"] = extra["httpReferer"]
    if extra.get("xTitle"):
        extra_headers["X-Title"] = extra["xTitle"]

    try:
        p = Provider(body.provider)
        handler = p.handler()
        result = await handler.validate(body.apiKey, extra)
        resp = ProviderValidateResponse(
            valid=result.valid,
            error=result.error,
            models=result.models,
        )
        # Attach extra headers if needed
        if extra_headers and hasattr(resp, 'extra_headers'):
            resp.extra_headers = extra_headers
        return resp
    except (ValueError, ModuleNotFoundError):
        # Fallback for custom providers
        base_url = _get_base_url(body.provider, body.baseUrl, extra)
        if base_url:
            return await _validate_openai_compatible(body.apiKey, base_url, extra_headers)
        return ProviderValidateResponse(valid=False, error=f"Unknown provider: {body.provider}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/providers/testing.py
git commit -m "refactor(testing): dispatch to provider handlers"
```

---

### Task 21: Refactor models.py — dispatch ke handler

**Files:**
- Modify: `backend/app/routers/providers/models.py`

- [ ] **Step 1: Simplify _fetch_builtin_models()**

```python
async def _fetch_builtin_models(
    provider: str, api_key: str, data: dict,
) -> list[dict]:
    """Fetch models from a built-in provider using the Provider handler."""
    # Qoder has special COSY-signed handling
    if provider == "qoder":
        return await _fetch_qoder_models(api_key, data)

    token = data.get("accessToken") or api_key
    if not token:
        raise HTTPException(status_code=401, detail="No valid token found")

    try:
        p = Provider(provider)
        handler = p.handler()
        models_raw = await handler.fetch_models(token, data)
        return [handler._normalize_model(m) for m in models_raw if handler._normalize_model(m).get("id")]
    except (ValueError, ModuleNotFoundError):
        # Fallback for providers not in new system
        return await _fetch_fallback(provider, api_key)
    except httpx.ConnectError:
        p = Provider(provider)
        raise HTTPException(status_code=502, detail=f"Cannot connect to {p.base_url()}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch models: {e.response.status_code}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/providers/models.py
git commit -m "refactor(models): dispatch to provider handlers"
```

---

### Task 22: Refactor helpers.py — move special cases ke handler

**Files:**
- Modify: `backend/app/providers/provider.py`
- Modify: `backend/app/routers/providers/helpers.py`

- [ ] **Step 1: Add resolve_base_url() to Provider class**

Tambah method ke `Provider`:

```python
def resolve_base_url(self, data: dict | None = None) -> str:
    """Resolve effective base URL using handler (handles region-aware providers)."""
    return self.handler()._resolve_base_url(data)
```

- [ ] **Step 2: Update _get_base_url() di helpers.py**

```python
def _get_base_url(provider: str, body_base_url: Optional[str] = None, extra_data: Optional[dict] = None) -> str:
    """Resolve the effective base URL for a provider using handler."""
    if body_base_url:
        return body_base_url.rstrip("/")

    try:
        p = Provider(provider)
        return p.resolve_base_url(extra_data)
    except (ValueError, ModuleNotFoundError):
        if extra_data and extra_data.get("baseUrl"):
            return extra_data["baseUrl"].rstrip("/")
        defaults = _get_provider_config(provider)
        return defaults.get("baseUrl", "").rstrip("/")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/provider.py backend/app/routers/providers/helpers.py
git commit -m "refactor(helpers): use handler for base URL resolution"
```

---

### Task 23: Refactor connections.py — dispatch validation ke handler

**Files:**
- Modify: `backend/app/routers/providers/connections.py`

- [ ] **Step 1: Simplify auto-validate in create_provider()**

Replace the validation section in `create_provider()` (around line 120-160):

```python
    # Auto-validate on create
    if body.apiKey and test_status == "unknown":
        try:
            from app.routers.providers.validation import _validate_provider
            vr = await _validate_provider(body.provider, body.apiKey, body.providerSpecificData or {})
            if vr:
                test_status = "connected" if vr.valid else "error"
        except Exception:
            test_status = "untested"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/providers/connections.py
git commit -m "refactor(connections): use handler for auto-validation"
```

---

### Task 24: Run tests dan verifikasi

- [ ] **Step 1: Run existing tests**

```bash
cd /home/mint/dev/9router-fastapi
python -m pytest backend/tests/ -v -k "provider" --tb=short
```

Expected: All provider-related tests pass

- [ ] **Step 2: Verify handler loading**

```bash
python -c "
from app.providers.provider import Provider

# Test handler loading
p = Provider('anthropic')
h = p.handler()
print(f'Anthropic handler: {type(h).__name__}')

p = Provider('openai')
h = p.handler()
print(f'OpenAI handler: {type(h).__name__}')

p = Provider('gemini')
h = p.handler()
print(f'Gemini handler: {type(h).__name__}')

# Test fallback (provider without custom handler)
p = Provider('deepseek')
h = p.handler()
print(f'DeepSeek handler: {type(h).__name__}')
"
```

Expected output:
```
Anthropic handler: AnthropicHandler
OpenAI handler: BaseProviderHandler
Gemini handler: GeminiHandler
DeepSeek handler: BaseProviderHandler
```

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "feat(providers): complete handler system integration"
```

---

## Success Criteria

1. `validation.py` dispatches ke provider handlers (tidak ada if/elif chain)
2. `testing.py` dispatches ke provider handlers
3. `models.py` dispatches ke handler.fetch_models()
4. `helpers.py` uses handler untuk base URL resolution
5. `connections.py` uses handler untuk auto-validation
6. Setiap provider dengan custom validation punya `handler.py`
7. `Provider("anthropic").handler()` returns `AnthropicHandler`
8. Providers tanpa custom handler tetap work (fallback ke `BaseProviderHandler`)
9. Semua existing tests pass

---

## Migration Notes

- **Backward compatibility:** Fungsi lama `_validate_anthropic()`, `_validate_google()`, dll masih ada sebagai wrapper
- **Incremental:** Bisa diimplementasi per-provider (satu handler per commit)
- **Fallback:** Provider tanpa handler tetap work via `BaseProviderHandler`
- **Testing:** Setiap handler bisa di-test secara independen

---

## Dependency Order

```
Task 1  (base.py) ─────────────────────┐
Task 2  (provider.py) ─────────────────┤
Task 3-18 (handler.py per provider) ───┼──► Task 19-23 (refactor routers)
                                        │
Task 24 (verify) ◄─────────────────────┘
```

Tasks 3-18 bisa parallel. Tasks 19-23 harus sequential (satu file per commit).
