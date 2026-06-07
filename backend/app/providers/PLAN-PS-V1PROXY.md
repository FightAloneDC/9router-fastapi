# Plan: Full PS Integration — v1_proxy

**Goal**: Semua provider-specific logic di `backend/app/routers/v1_proxy/` harus dispatch ke handler/adapter di `backend/app/providers/` atau `backend/app/services/`. Router layer hanya orchestrator.

**Prinsip**: Router = thin orchestrator. Provider-specific URL, headers, body transforms → handler/adapter.

---

## Current State (Audit)

| File | Status | Issues |
|------|--------|--------|
| `shared.py` | ✅ PS | Delegate ke handler via `Provider().handler()` |
| `chat.py` | ⚠️ | Qoder-specific request building (lines 85-102) |
| `messages.py` | ⚠️ | Hardcoded `_CLAUDE_FORMAT_PROVIDERS` + legacy `_get_provider_proxy_config()` |
| `audio.py` | ⚠️ | Azure STT-specific URL/auth override (lines 412-425) |
| `images.py` | ✅ PS | Adapter pattern, dispatch ke `IMAGE_ADAPTERS` |
| `embeddings.py` | ✅ PS | Delegate ke handler via shared.py |
| `models.py` | ✅ PS | Data layer only (`infer_model_type`) |
| `web.py` | ⚠️ | Hardcoded `_FETCH_ADAPTERS` (URLs, auth) untuk 4 provider |
| `search.py` | ✅ PS | Adapter pattern, dispatch ke `search_adapters` |
| `responses.py` | ✅ PS | Translation layer, no provider logic |

---

## Plan

### Phase 1: chat.py — Qoder Request Building

**Problem**: Router punya `if target.provider == "qoder"` branch yang memanggil `build_qoder_request()` dari proxy service. Ini provider-specific dispatch yang seharusnya generic.

**Current code** (`chat.py:85-102`):
```python
if target.provider == "qoder":
    from app.services.proxy import build_qoder_request
    conn_result = await db.execute(...)
    conn = conn_result.scalar_one_or_none()
    if conn:
        conn_data = _json.loads(conn.data) if conn.data else {}
        raw_body, target.headers = await build_qoder_request(target, body, conn_data)
```

**Fix approach**: Pindahkan Qoder-specific request transform ke handler method `build_request_body()`. Sudah ada di Qoder handler. Yang perlu diubah adalah router-nya — buat generic dispatch:

```python
# Handler returns (raw_bytes, signed_headers) or (None, None) for standard providers
raw_body, signed_headers = await _build_provider_request(target, body, conn_data)
if signed_headers:
    target.headers = signed_headers
```

**New helper in `shared.py`**:
```python
async def _build_provider_request(
    target: ProxyTarget, body: dict, conn_data: dict
) -> tuple[bytes | None, dict[str, str] | None]:
    """Build provider-specific request body if handler supports it.

    Returns (raw_body_bytes, signed_headers) or (None, None) for standard providers.
    """
    try:
        from app.providers.provider import Provider
        p = Provider(target.provider)
        handler = p.handler()
        if hasattr(handler, 'build_request_body'):
            raw_body, headers = await handler.build_request_body(target.model, body, conn_data)
            return raw_body, headers
    except (ValueError, ModuleNotFoundError):
        pass
    return None, None
```

**Verify**: Test Qoder streaming + non-streaming chat. Test standard providers unchanged.

---

### Phase 2: messages.py — Format Detection

**Problem**: 
1. `_CLAUDE_FORMAT_PROVIDERS` hardcoded set di router
2. `_get_provider_proxy_config()` legacy function dipakai untuk detect format

**Current code** (`messages.py:37,112-114`):
```python
_CLAUDE_FORMAT_PROVIDERS: set[str] = {"anthropic", "glm", "kimi", "minimax", "minimax-cn", "claude"}

provider_cfg: dict = _get_provider_proxy_config(target.provider)
upstream_format: str = provider_cfg.get("format", "openai")
is_claude_upstream: bool = upstream_format == "claude" or target.provider in _CLAUDE_FORMAT_PROVIDERS
```

**Fix approach**: Gunakan `FORMAT` field dari provider config. Tambah `FORMAT = "claude"` di config provider yang natively speak Claude Messages API.

**Changes**:
1. Tambah `FORMAT: str = "claude"` di config providers: anthropic, glm, kimi, minimax, minimax_cn
   - anthropic/config.py → `AnthropicConfig` tambah `FORMAT: str = "claude"`
   - glm/config.py → `GlmConfig` tambah `FORMAT: str = "claude"`
   - kimi/config.py → tambah `FORMAT: str = "claude"`
   - minimax/config.py → tambah `FORMAT: str = "claude"`
   - minimax_cn/config.py → tambah `FORMAT: str = "claude"`
   - claude provider (jika ada) → tambah `FORMAT: str = "claude"`
2. Ganti detection logic:
```python
from app.providers.provider import Provider
try:
    p = Provider(target.provider)
    c = p.config()
    upstream_format = c.FORMAT
except (ValueError, ModuleNotFoundError):
    upstream_format = "openai"
is_claude_upstream = upstream_format == "claude"
```
3. Hapus `_CLAUDE_FORMAT_PROVIDERS` set
4. Hapus import `_get_provider_proxy_config` dari messages.py

**Note**: `_get_provider_proxy_config()` masih dipakai di `proxy.py:493` sebagai fallback di `_resolve_base_url()` — itu proxy service layer, bukan router. Tidak dihapus, hanya import di messages.py yang dihapus.

**Verify**: Test /v1/messages dengan anthropic, glm, kimi, minimax. Test /v1/messages dengan openai-format provider (auto-translate).

---

### Phase 3: audio.py — Azure STT URL/Auth

**Problem**: Azure STT punya URL construction khusus di router (`audio.py:412-425`):
```python
if provider_id == "azure":
    endpoint = conn_data.get("azureEndpoint") or base_url
    deployment = conn_data.get("deployment", "whisper")
    api_version = conn_data.get("apiVersion", "2024-06-01")
    extra_url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        f"/audio/transcriptions?api-version={api_version}"
    )
```
Dan auth header override (`audio.py:443-444`):
```python
auth_header="api-key" if provider_id == "azure" else "Authorization",
auth_prefix="" if provider_id == "azure" else "Bearer ",
```

**Fix approach**: Pindahkan ke Azure handler sebagai `build_stt_url()` dan `build_stt_headers()` methods. Atau lebih sederhana — buat helper function di Azure provider folder.

**New method in Azure handler** (`backend/app/providers/azure/handler.py`):
```python
def build_stt_request(self, data: dict, model: str) -> tuple[str, dict[str, str]]:
    """Build STT URL and headers for Azure deployment."""
    endpoint = data.get("azureEndpoint") or self.config.BASE_URL
    deployment = data.get("deployment", "whisper")
    api_version = data.get("apiVersion", "2024-06-01")
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/audio/transcriptions?api-version={api_version}"
    headers = {"api-key": data.get("apiKey", "")}
    return url, headers
```

**Router change** (`audio.py`):
```python
extra_url = None
stt_headers = None
if provider_id == "azure":
    from app.providers.azure.handler import AzureHandler
    from app.providers.azure.config import AzureConfig
    handler = AzureHandler(AzureConfig(BASE_URL=base_url))
    extra_url, stt_headers = handler.build_stt_request(conn_data, model_id)
```

Actually, lebih baik buat generic — cek apakah handler punya `build_stt_request`:
```python
extra_url = None
auth_header_override = None
auth_prefix_override = None
try:
    p = Provider(provider_id)
    handler = p.handler()
    if hasattr(handler, 'build_stt_request'):
        extra_url, stt_auth = handler.build_stt_request(conn_data, model_id)
        auth_header_override = stt_auth.get("auth_header")
        auth_prefix_override = stt_auth.get("auth_prefix")
except (ValueError, ModuleNotFoundError):
    pass
```

**Verify**: Test Azure STT, test other STT providers (openai, groq, deepgram).

---

### Phase 4: web.py — Fetch Adapters

**Problem**: `_FETCH_ADAPTERS` dict hardcoded URLs dan auth config untuk 4 provider:
```python
_FETCH_ADAPTERS = {
    "jina-reader": {
        "base_url": "https://r.jina.ai",
        "method": "GET",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        ...
    },
    "tavily": {"base_url": "https://api.tavily.com/extract", ...},
    "exa": {"base_url": "https://api.exa.ai/contents", ...},
    "firecrawl": {"base_url": "https://api.firecrawl.dev/v1/scrape", ...},
}
```

**Fix approach**: Pindahkan ke masing-masing provider handler sebagai `build_webfetch_request()` method.

**New method pattern di masing-masing handler**:
```python
# jina_reader handler
def build_webfetch_request(self, url: str, fmt: str, api_key: str) -> tuple[str, dict, str | None, dict | None]:
    """Build web fetch request. Returns (method, headers, full_url, body)."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return "GET", headers, f"{self.config.BASE_URL}/{url}", None

# tavily handler
def build_webfetch_request(self, url: str, fmt: str, api_key: str) -> tuple[str, dict, str | None, dict | None]:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return "POST", headers, self.config.BASE_URL, {"urls": [url], "format": fmt}
```

**Router change** (`web.py`):
```python
# Replace _FETCH_ADAPTERS with handler dispatch
from app.providers.provider import Provider
try:
    p = Provider(provider_id)
    handler = p.handler()
    method, headers, fetch_url, body_data = handler.build_webfetch_request(url, fmt, api_key)
except (ValueError, ModuleNotFoundError, AttributeError):
    return JSONResponse(status_code=501, content={"error": {"message": f"Provider {provider_id} does not support web fetch"}})
```

**Also**: Update `_resolve_webfetch_connection()` to use handler's `SERVICE_KINDS` instead of `_get_provider_config()`.

**Verify**: Test web fetch with jina-reader, tavily, exa, firecrawl.

---

## Execution Order

```
Phase 1 (chat.py)     → verify: Qoder + standard chat still works
Phase 2 (messages.py)  → verify: Claude-format + OpenAI-format providers via /v1/messages
Phase 3 (audio.py)     → verify: Azure STT + other STT providers
Phase 4 (web.py)       → verify: All 4 web fetch providers
```

Each phase is independent.

---

## Success Criteria

- [x] No `if provider == "xxx"` branches in v1_proxy router files
- [x] No hardcoded provider URLs in v1_proxy
- [x] No hardcoded auth header/prefix in v1_proxy
- [x] All provider-specific transforms via handler methods or adapter functions
- [x] `_CLAUDE_FORMAT_PROVIDERS` removed from messages.py
- [x] `_FETCH_ADAPTERS` removed from web.py
- [x] `_get_provider_proxy_config()` import removed from messages.py
- [ ] All existing endpoints work unchanged

## Result

**v1_proxy changes**: 4 files modified, 4 new handler files created
**Provider config changes**: 5 configs updated (FORMAT = "claude")
**Net**: -125 lines across v1_proxy + provider handlers
