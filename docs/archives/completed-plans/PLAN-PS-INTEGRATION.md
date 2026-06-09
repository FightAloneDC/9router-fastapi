# Plan: Full Provider-Specific (PS) Integration

**Goal**: Semua provider-specific logic (validate, fetch models, build request) harus via `backend/app/providers/`. Router layer (`backend/app/routers/providers/`) hanya orchestrator — terima request, dispatch ke handler, return response.

**Prinsip**: 
- 1 provider = 1 folder
- Router = thin orchestrator, no provider-specific logic
- Shared helpers di `base.py`, bukan di router

---

## Current State (Audit)

| File | Status | Issues |
|------|--------|--------|
| `validation.py` | ✅ PS | Clean dispatch via `Provider.handler().validate()` |
| `connections.py` | ✅ PS | No provider-specific logic |
| `constants.py` | ✅ PS | Data only, no logic |
| `testing.py` | ⚠️ Partial | Inline config for nodes, OpenRouter headers leak, dead fallback |
| `models.py` | ⚠️ Partial | Inline config for nodes, dead fallback path |
| `nodes.py` | ❌ Not PS | Full inline httpx validation for 3 node types |
| `helpers.py` | ⚠️ Dead code | `_get_validation_type()` has no callers |

### Bugs Found
- `testing.py:247` imports `get_provider_models` from `models.py` — function doesn't exist. Runtime crash.

---

## Plan

### Phase 1: Node Validation → PS

**Problem**: `nodes.py:252-378` has 130 lines of inline httpx validation for 3 node types (openai-compatible, anthropic-compatible, custom-embedding). This should use the existing `BaseProviderHandler` helpers.

**File**: `backend/app/routers/providers/nodes.py`

**Changes**:
```python
# BEFORE (130 lines of inline httpx)
async def validate_provider_node(body):
    if body.type == "custom-embedding":
        # 30 lines inline httpx...
    if body.type == "anthropic-compatible":
        # 40 lines inline httpx...
    # openai-compatible default
    # 60 lines inline httpx...

# AFTER (thin dispatch ~30 lines)
async def validate_provider_node(body):
    from app.providers.base import BaseProviderConfig, BaseProviderHandler
    
    config = _build_node_config(body)
    handler = BaseProviderHandler(config)
    
    if body.type == "custom-embedding":
        result = await handler._validate_embedding(body.apiKey, body.modelId)
    elif body.type == "anthropic-compatible":
        result = await handler._validate_anthropic_compatible(body.apiKey, config.BASE_URL)
    else:
        result = await handler._validate_openai_compatible(body.apiKey, config.BASE_URL)
    
    return ProviderNodeValidateResponse(
        valid=result.valid, error=result.error, method=result.method
    )
```

**New helper needed in `base.py`**:
```python
async def _validate_embedding(self, api_key: str, model_id: str) -> ValidateResult:
    """Embedding validation: POST /embeddings with model + input."""
```

**Verify**: Test node validation endpoint with all 3 types.

---

### Phase 2: Testing.py → PS

**Problem**: `_test_provider_connection()` builds inline `BaseProviderConfig` for nodes (lines 60-78). `validate_provider()` has OpenRouter header logic (lines 118-122) that belongs in handler.

**File**: `backend/app/routers/providers/testing.py`

**Changes**:

#### 2a. Node connection testing
```python
# BEFORE (inline config building)
if node_type == "anthropic-compatible":
    config = BaseProviderConfig(
        PROVIDER_NAME=node.name or node.id,
        AUTH_HEADER="x-api-key",
        EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
        ...
    )
else:
    config = BaseProviderConfig(...)

# AFTER (delegate to node handler or reuse validate_provider_node logic)
# Option: Create a helper in base.py that builds config from node data
```

**New helper needed in `base.py` or `helpers.py`**:
```python
def build_node_handler(node: ProviderNode, node_data: dict) -> BaseProviderHandler:
    """Build a handler from a ProviderNode for validation/testing."""
```

#### 2b. Remove OpenRouter header leak from validate endpoint
```python
# BEFORE (testing.py:118-122 — OpenRouter-specific logic in router)
extra_headers = {}
if extra.get("httpReferer"):
    extra_headers["HTTP-Referer"] = extra["httpReferer"]
if extra.get("xTitle"):
    extra_headers["X-Title"] = extra["xTitle"]

# AFTER (handler already does this — OpenRouter handler reads from data)
p = Provider(body.provider)
handler = p.handler()
result = await handler.validate(body.apiKey, extra)
```

#### 2c. Remove dead fallback path
Lines 91-102: `_get_provider_config()` fallback when `Provider()` fails. This path is redundant — if provider is unknown, return error, don't try to build config manually.

#### 2d. Fix `get_provider_models` bug
Line 247 imports `get_provider_models` from `models.py` but function doesn't exist. Either:
- Create it in `models.py`, or
- Use `handler.fetch_models()` directly

**Verify**: Test connection test, batch test, validate endpoints.

---

### Phase 3: Models.py → PS

**Problem**: `_fetch_node_models()` (lines 25-63) builds inline config. `_fetch_fallback()` (lines 101-123) is dead path.

**File**: `backend/app/routers/providers/models.py`

**Changes**:

#### 3a. Node model fetching
```python
# BEFORE (inline config)
if node.type == "anthropic-compatible":
    config = BaseProviderConfig(
        AUTH_HEADER="x-api-key",
        EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
        ...
    )

# AFTER (reuse build_node_handler from Phase 2)
handler = build_node_handler(node, node_data)
models_raw = await handler.fetch_models(api_key, node_data)
```

#### 3b. Remove `_fetch_fallback()`
Dead path — `_fetch_builtin_models()` catches `ValueError/ModuleNotFoundError` and calls `_fetch_fallback()`. But `_fetch_fallback()` does the same thing `_fetch_builtin_models()` already does (build config, fetch models). Remove it.

```python
# BEFORE
except (ValueError, ModuleNotFoundError):
    return await _fetch_fallback(provider, api_key)

# AFTER
except (ValueError, ModuleNotFoundError):
    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
```

#### 3c. Remove unused imports
- `fetch_models_header_auth` — only used in dead `_fetch_fallback()` and `_fetch_node_models()`
- `_normalize_model` — only used in dead code paths (`_fetch_node_models` line 58, `_fetch_fallback` line 118). Live path uses `handler._normalize_model()` (line 80)
- `_parse_openai_models` — imported but never called in this file

**Verify**: Test fetch models endpoint for built-in and node-based providers.

---

### Phase 4: Helpers.py Cleanup

**File**: `backend/app/routers/providers/helpers.py`

**Changes**:
1. Remove `_get_validation_type()` (lines 44-47) — no callers
2. Remove `_parse_openai_models()` (lines 191-197) — no callers in router files (only imported but unused in models.py)
3. Remove `_get_models_error_message()` and `_get_chat_error_message()` (lines 210-229) — only used in `nodes.py` inline validation, which Phase 1 removes

**Verify**: Grep for all removed function names to confirm no callers remain.

---

## Execution Order

```
Phase 1 (nodes.py)  → verify: node validation works for all 3 types
Phase 2 (testing.py) → verify: connection test, batch test, validate work
Phase 3 (models.py)  → verify: fetch models works for built-in + node providers
Phase 4 (helpers.py) → verify: no broken imports
```

Each phase is independent — can be done and committed separately.

---

## Success Criteria

- [x] No inline `httpx` calls in `backend/app/routers/providers/` for provider-specific operations
- [x] No `BaseProviderConfig` construction in router files (except `_build_node_handler` helper)
- [x] No provider-specific header logic in router files (OpenRouter leak removed)
- [x] All validation via `handler.validate()` or `handler._validate_*()` helpers
- [x] All model fetching via `handler.fetch_models()`
- [x] No dead functions in `helpers.py`
- [x] `testing.py:247` bug fixed (replaced non-existent `get_provider_models` with `data.get("models")`)
- [ ] All existing tests pass

## Result

5 files changed, 139 insertions(+), 283 deletions(-) — net reduction of 144 lines.
