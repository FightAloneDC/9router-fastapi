# Plan: Kilo Provider Integration — Kilo Code + Kilo Gateway

> **Created:** 2026-05-19
> **Status:** Complete
> **Requested by:** User

---

## 1. Background

Currently, only `Kilo Code` (OAuth provider) exists. User reports:
- ✅ OAuth authentication works
- ❌ Test connection does not work
- ❌ Fetch models does not work
- ✅ Test model works (can do a chat request)

The original 9router (Next.js) also lacks test connection and fetch models for Kilo Code, but test model works.

User requests adding `Kilo Gateway` as a separate API key provider alongside `Kilo Code`, with shared prefix `kilo`.

---

## 2. Provider Architecture

| Provider | ID | Auth Type | Alias | Base URL | Purpose |
|----------|-----|-----------|-------|----------|---------|
| Kilo Code | `kilocode` | OAuth (Device Code) | `kc` | `https://api.kilo.ai/api/openrouter` | OAuth-based access |
| Kilo Gateway | `kilo-gateway` | API Key | `kg` | `https://api.kilo.ai/api/gateway` | API key-based access |

Both share:
- **Prefix:** `kilo` (for model routing)
- **Fetch models URL:** `https://api.kilo.ai/api/gateway/models` (no auth required)
- **Test connection method:** Direct chat with model `kilo-auto/free`

---

## 3. Implementation Tasks

### Task 1: Backend — Add Kilo Gateway provider config + validation
**Assignee:** 9router-backend
**Scope:**
- Add `kilo-gateway` to `PROVIDER_DEFAULTS` in `providers.py`
- Add `_validate_openai_chat()` validation function (test via direct chat)
- Add handling in `_test_provider_connection` for `openai-chat` validation type
- Add handling in `validate_provider` endpoint for `openai-chat` validation type
- Add `kilo-gateway` to `SUGGESTED_MODELS_FILTERS` in `providers.py`
- Add `kilo-gateway` to `PROVIDER_CONFIGS` in `proxy.py`
- Add `"kg": "kilo-gateway"` to `ALIAS_TO_ID` in `proxy.py`

**Files:**
- `backend/app/routers/providers.py`
- `backend/app/services/proxy.py`

### Task 2: Frontend — Add Kilo Gateway provider definition + UI
**Assignee:** 9router-frontend
**Scope:**
- Add `kilo-gateway` to `APIKEY_PROVIDERS` in `frontend/src/constants/providers.js`
- Configure `passthroughModels: true` and `modelsFetcher`
- Ensure AddKeyModal uses standard API key template for Kilo Gateway

**Files:**
- `frontend/src/constants/providers.js`

### Task 3: Auditor — Review implementation vs requirements
**Assignee:** 9router-auditor
**Scope:**
- Verify Kilo Gateway config matches user requirements
- Verify test connection uses `kilo-auto/free` model
- Verify fetch models uses `https://api.kilo.ai/api/gateway/models`
- Verify both providers share `kilo` prefix
- Check for any missing pieces vs original 9router

### Task 4: QA — Test Kilo Gateway end-to-end
**Assignee:** 9router-qa
**Scope:**
- Test add connection with API key
- Test connection via direct chat
- Test fetch models from gateway URL
- Test model chat via proxy
- Verify Kilo Code OAuth still works

### Task 5: Docs — Document Kilo provider setup
**Assignee:** 9router-docs
**Scope:**
- Document both Kilo Code and Kilo Gateway providers
- Document test connection method
- Document fetch models behavior
- Update provider inventory if exists

---

## 4. Dispatch Strategy

```
Task 1 (Backend) + Task 2 (Frontend) → PARALLEL (different roles)
    ↓
Task 3 (Auditor) → Review after Task 1 + 2 complete
    ↓
Task 4 (QA) → Test after Auditor approves
    ↓
Task 5 (Docs) → Document after QA confirms
```

---

## 5. Validation Pattern

### Test Connection (via direct chat)
```python
POST https://api.kilo.ai/api/gateway/chat/completions
Headers: Authorization: Bearer {api_key}, Content-Type: application/json
Body: {"model": "kilo-auto/free", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
```

### Fetch Models (no auth)
```
GET https://api.kilo.ai/api/gateway/models
```

---

## 6. Success Criteria

- [x] Kilo Gateway appears in provider list
- [x] Can add connection with API key
- [x] Test connection succeeds with valid key
- [x] Fetch models returns model list
- [x] Can chat through proxy with Kilo Gateway
- [x] Kilo Code OAuth still works unchanged
- [x] Both share `kilo` prefix for model routing
