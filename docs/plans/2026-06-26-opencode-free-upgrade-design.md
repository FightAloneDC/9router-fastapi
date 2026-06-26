# OpenCode Free — UI/UX & Handler Upgrade

**Date:** 2026-06-26
**Scope:** OpenCode Free provider only (`opencode`, alias `oc`)
**Reference:** Node.js source at `~/dev/9router/` + NVIDIA as UI/UX benchmark

---

## Background

OpenCode Free is a unique provider — adopted from the OpenCode CLI desktop app,
not a standard API key provider. It impersonates the desktop client by sending
`Authorization: Bearer public` + `x-opencode-client: "desktop"` headers.

In the original Node.js 9Router, OpenCode Free has:
- Custom `OpenCodeExecutor` with dedicated headers and URL building
- `NoAuthProxyCard` instead of standard connections card
- Model filter that includes `big-pickle` (free model without `-free` suffix)

The current FastAPI implementation is incomplete:
- No custom handler — uses generic `BaseProviderHandler` with empty API key
- `SERVICE_KINDS` is empty (should be `["llm"]`)
- No notice text explaining what OpenCode Free is
- Model filter misses `big-pickle`
- UI shows standard connections management instead of simplified noAuth flow

---

## Changes

### 1. Backend: Custom Handler (`providers/opencode/handler.py`) — NEW

Create `OpencodeHandler(BaseProviderHandler)` with:

**`validate()`:**
- NoAuth provider — always return `ValidateResult(valid=True, latency_ms=0)`
- No API key check needed

**`build_upstream_url()`:**
- Override to route to `{base_url}/zen/v1/chat/completions`
- NOT the default `/chat/completions`

**`build_headers()`:**
- Return fixed headers impersonating OpenCode desktop CLI:
  ```python
  {
      "Content-Type": "application/json",
      "Authorization": "Bearer public",
      "x-opencode-client": "desktop",
  }
  ```
- Ignore the `api_key` parameter — this is a noAuth provider

**`fetch_models()`:**
- Fetch from `https://opencode.ai/zen/v1/models`
- Apply `opencode-free` filter: models ending with `-free` OR `big-pickle`
- Return normalized model list

### 2. Backend: Models (`providers/opencode/models.py`) — NEW

Dedicated model fetching module (same pattern as NVIDIA):

```python
async def fetch_models(api_key: str = "") -> list[dict]:
    """Fetch free models from OpenCode zen endpoint."""
    # HTTP GET to https://opencode.ai/zen/v1/models
    # Filter: id ends with "-free" OR id == "big-pickle"
    # Return [{id, name}] normalized list
```

### 3. Backend: Config Update (`providers/opencode/config.py`)

**`OpencodeConfig`:**
- `SERVICE_KINDS`: change from `[]` to `["llm"]`

**`OpencodeMetadata`:**
- Add `notice: dict | None = {"text": "Free AI models via OpenCode CLI. No API key required."}`

No other config changes — `NO_AUTH`, `PASSTHROUGH_MODELS`, `MODELS_FETCHER` stay as-is.

### 4. Backend: Model Filter Update (`routers/providers/constants.py`)

Update the `opencode-free` filter lambda:

```python
"opencode-free": lambda models: [
    {"id": m.get("id"), "name": m.get("id")}
    for m in models
    if m.get("id", "").endswith("-free")
       or m.get("id") == "big-pickle"
],
```

### 5. Frontend: providers-v1.js Update

Sync the hardcoded `opencode` entry in `FREE_PROVIDERS` with new metadata:

```javascript
opencode: {
    id: "opencode",
    alias: "oc",
    name: "OpenCode Free",
    icon: "Terminal",
    color: "#E87040",
    textIcon: "OC",
    noAuth: true,
    passthroughModels: true,
    modelsFetcher: { url: "https://opencode.ai/zen/v1/models", type: "opencode-free" },
    serviceKinds: ["llm"],  // ← NEW
    notice: { text: "Free AI models via OpenCode CLI. No API key required." },  // ← NEW
},
```

### 6. Frontend: ProviderDetailPage.jsx Update

Simplify the UI for OpenCode Free (and other noAuth providers) to match NVIDIA-style UX
but without connection management complexity.

**Keep (same as NVIDIA):**
- Header: icon, name, notice text, service kind badges
- Chat Test Playground — works directly without connections
- Available Models card — fetch, enable/disable, search

**Change:**
- Replace complex connections card with simplified noAuth status:
  - Show "Connected" status badge (auto-created via one-click Connect)
  - Show proxy pool selector (UI only, not wired to httpx yet)
  - No edit/test/delete connection buttons
  - No priority arrows or strategy selector
- One-click "Connect" button when no connection exists (already implemented)

**What to remove for noAuth providers:**
- Connection rows with edit/test/delete
- Strategy selector (fill first, round robin, random)
- "Add Connection" / "Add API Key" button
- OAuth modal trigger

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `backend/app/providers/opencode/handler.py` | CREATE | Custom handler with Bearer public + desktop header |
| `backend/app/providers/opencode/models.py` | CREATE | Dedicated model fetching + filter |
| `backend/app/providers/opencode/config.py` | UPDATE | SERVICE_KINDS + notice |
| `backend/app/routers/providers/constants.py` | UPDATE | Filter include big-pickle |
| `frontend/src/constants/providers-v1.js` | UPDATE | Sync metadata (serviceKinds, notice) |
| `frontend/src/pages/ProviderDetailPage.jsx` | UPDATE | Simplified noAuth UI |

**NOT touched:** Qoder, NVIDIA, any other provider, any `-v*` backup files.

---

## Out of Scope

- Proxy pool wiring to httpx (UI selector only, actual proxy routing deferred)
- Custom modals (noAuth providers don't need OAuth/key modals)
- OpenCode Go (separate provider, separate scope)
- CLI Tools page (separate system)

---

## Success Criteria

1. `/providers/opencode` card shows notice and "Ready" badge in ProvidersPage
2. Detail page shows NVIDIA-style UI (header, notice, models, chat test)
3. One-click "Connect" creates noAuth connection successfully
4. Fetch models works (filters `-free` + `big-pickle`)
5. Chat test sends `Bearer public` + `x-opencode-client: desktop` to `zen/v1/chat/completions`
6. Proxy pool selector appears in detail page (UI only)
7. No changes to any other provider's behavior
