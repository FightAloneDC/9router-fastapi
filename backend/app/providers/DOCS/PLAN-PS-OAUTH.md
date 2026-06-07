# PLAN: PS Integration for OAuth (oauth.py + oauth_providers.py)

**Severity:** 🔴 CRITICAL (~3335 lines duplicated across 2 files)
**Date:** 2026-06-07

---

## Problem

Two files contain nearly identical OAuth logic for 16 providers:
- `backend/app/services/oauth.py` (1819 lines) — PKCE, configs, OAuthService class, handler classes, device code functions, module-level instances
- `backend/app/services/oauth_providers.py` (1516 lines) — duplicated configs, per-provider functions, dispatch functions

Both have their own config constants, their own token exchange logic, their own device code flow handlers. Massive duplication.

## Providers (16 total)

| Provider | Flow | Has Handler? |
|----------|------|-------------|
| claude | Auth Code + PKCE | In oauth.py (OAuthService) |
| codex | Auth Code + PKCE | In oauth.py (CodexHandler) |
| openai | Auth Code + PKCE | In oauth.py (OAuthService) |
| gemini | Auth Code (no PKCE) | In oauth.py (OAuthService) |
| qwen | Device Code | In oauth.py (OAuthService) |
| qoder | Device Token (custom) | In oauth.py (OAuthService) |
| iflow | Auth Code (no PKCE) | In oauth.py (OAuthService) |
| antigravity | Auth Code (no PKCE) | In oauth.py (OAuthService) |
| github | Device Code | In oauth.py (GitHubHandler) |
| kiro | Device Code (custom) | In oauth.py (KiroHandler) |
| cursor | Import Token | In oauth.py (CursorHandler) |
| kimi-coding | Device Code | In oauth.py (OAuthService) |
| kilocode | Device Code | In oauth.py (OAuthService) |
| cline | Auth Code (special) | In oauth.py (OAuthService) |
| gitlab | Auth Code | In oauth.py (GitLabHandler) |
| codebuddy | Device Code | In oauth.py (OAuthService) |

## Router Calls

From `backend/app/routers/oauth.py`:
```python
from app.services import oauth_providers
from app.services.oauth import kiro_handler, cursor_handler

# Used:
oauth_providers.generate_auth_data(provider, redirect_uri)
oauth_providers.exchange_tokens(provider, code, redirect_uri, ...)
oauth_providers.get_provider(provider)
oauth_providers.request_device_code(provider, code_challenge, ...)
oauth_providers.poll_for_token(provider, device_code, ...)
oauth_providers.map_tokens(provider, token_data)
kiro_handler  # direct access
cursor_handler  # direct access
```

## Approach

### Phase 1: Create per-provider OAuth handlers in `backend/app/providers/<provider>/oauth.py`

Each provider gets a small OAuth handler class with methods:
- `get_config() → dict` — returns OAuth config (client IDs, URLs, scopes)
- `build_auth_url(redirect_uri, state, code_challenge) → str` — builds authorization URL
- `exchange_code(code, redirect_uri, code_verifier, state) → dict` — exchanges auth code for tokens
- `map_tokens(token_data) → dict` — maps provider-specific token response to standard format
- `request_device_code(code_challenge) → dict` — (device code flow only)
- `poll_device_code(device_code, code_verifier) → dict` — (device code flow only)
- `refresh_token(refresh_token) → dict` — refreshes access token

Not all methods apply to every provider — auth code providers skip device code methods and vice versa.

### Phase 2: Merge into single `backend/app/services/oauth.py`

- Keep PKCE utilities (shared, not provider-specific)
- Keep OAuthService class (generic auth code flow)
- Add `get_oauth_handler(provider)` dispatch function
- Add `generate_auth_data()`, `exchange_tokens()`, `request_device_code()`, `poll_for_token()`, `map_tokens()` as thin orchestrators
- Remove all provider-specific handler classes (moved to providers/)
- Remove all per-provider device code functions (moved to providers/)

### Phase 3: Delete `backend/app/services/oauth_providers.py`

All logic now lives in provider handlers. Router calls `get_oauth_handler(provider)`.

### Phase 4: Update router

Router imports from single `oauth.py` module, dispatches via handler.

---

## Execution Plan

### Step 1: Create base OAuth handler
- File: `backend/app/providers/oauth_base.py`
- Class: `BaseOAuthHandler` with default implementations
- Subclasses: `AuthCodeHandler`, `DeviceCodeHandler`, `ImportTokenHandler`

### Step 2: Create per-provider OAuth handlers (16 files)
- `backend/app/providers/<provider>/oauth.py`
- Move config + logic from both files
- Each handler is ~50-100 lines

### Step 3: Merge oauth.py + oauth_providers.py
- Keep PKCE utils, OAuthService class
- Add dispatch function `get_oauth_handler(provider)`
- Add thin orchestrator functions
- Delete oauth_providers.py

### Step 4: Update router
- Replace `oauth_providers.*` calls with handler dispatch
- Remove `kiro_handler`/`cursor_handler` imports

---

## File Structure (After)

```
backend/app/providers/
├── oauth_base.py              # BaseOAuthHandler, AuthCodeHandler, DeviceCodeHandler
├── claude/oauth.py            # ClaudeOAuthHandler
├── codex/oauth.py             # CodexOAuthHandler
├── openai/oauth.py            # OpenaiOAuthHandler
├── gemini/oauth.py            # GeminiOAuthHandler
├── qwen/oauth.py              # QwenOAuthHandler
├── qoder/oauth.py             # QoderOAuthHandler
├── iflow/oauth.py             # IflowOAuthHandler
├── antigravity/oauth.py       # AntigravityOAuthHandler
├── github/oauth.py            # GithubOAuthHandler
├── kiro/oauth.py              # KiroOAuthHandler
├── cursor/oauth.py            # CursorOAuthHandler
├── kimi_coding/oauth.py       # KimiCodingOAuthHandler
├── kilocode/oauth.py          # KilocodeOAuthHandler
├── cline/oauth.py             # ClineOAuthHandler
├── gitlab/oauth.py            # GitlabOAuthHandler
├── codebuddy/oauth.py         # CodebuddyOAuthHandler
```

## Risk Assessment

- **High risk** — OAuth is critical for auth flow, breaking it = can't log in
- **Mitigation** — test each provider's flow after migration
- **Complexity** — 16 providers × different flows = many edge cases
- **Approach** — incremental, one provider at a time, verify before moving next

## Estimated Scope

- New files: 17 (1 base + 16 providers)
- Deleted files: 1 (oauth_providers.py)
- Modified files: 2 (oauth.py, router/oauth.py)
- Lines moved: ~3000
- Lines added (handlers): ~1500
- Lines deleted (duplicates): ~3000
- Net: ~-1500 lines
