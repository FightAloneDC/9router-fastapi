# Backend DRY Opportunities — 9router-fastapi

**Audit Date**: 2026-08-11  
**Last Updated**: 2026-08-11 (after partial apply)  
**Branch**: `dev`  
**Scope**: `backend/app/` (routers, services, providers, schemas, utils)  
**Focus**: Behavior-coupled duplication that can be extracted without changing
behavior.  
**Companion**: `docs/investigations/backend-dry-opportunities-v1.md` covers
generic utilities (JSON parse, httpx factories, timing). Prefer this report
for v1_proxy / usage / settings DRY; treat v1 as optional lower-value ideas
(many are over-abstraction).

## Method

Read `AGENTS.md`, verified candidates by reading call sites, and updated this
doc after applying the safest extractions. PS Rule: provider-specific logic
stays in `backend/app/providers/<provider>/`.

---

## Applied (do not re-propose)

### Auth-token refresh on 401/403 / build failure — DONE

- **Was**: Inline `_try_qoder_token_refresh` + `provider == "qoder"` checks in
  chat / messages / responses (PS smell).
- **Now**:
  - `BaseProviderHandler.try_refresh_on_auth_error(db, connection_id)`
    (default `False`)
  - `QoderHandler.try_refresh_on_auth_error` → `try_refresh_connection`
  - `shared._maybe_refresh_on_auth_error(target, db, status_code=None)` —
    generic dispatch (401/403 gate when status set); no provider name in
    routers
  - `refreshed_ids` set in chat / messages / responses — refresh **once**
    per connection per request (avoids infinite retry loops)
- **Also fixed while applying**: `_build_provider_request` used to swallow
  `ValueError` from handlers (e.g. missing Qoder `model_config`), which let
  unsigned requests hang upstream. Only `Provider(...)` lookup failures are
  swallowed now; handler errors propagate to the refresh/exclude path.

### Cooldown / backoff mark-failed block — DONE

- **Was**: 7+ copies of read `backoffLevel` → `calculate_cooldown` →
  `mark_connection_unavailable` → `exclude_ids.add`.
- **Now**: `shared._mark_conn_failed(db, connection_id, status, detail,
  model, exclude_ids)` used by chat, messages, responses, embeddings,
  images, audio.
- **Preserved**: `chat.py` still has the 503 branch (exclude, no cooldown)
  *before* calling `_mark_conn_failed`.

---

## Remaining findings

### [Priority: High] Proxy fallback loop skeleton duplicated across v1 endpoints

- **Locations**:
  - `backend/app/routers/v1_proxy/chat.py` — `chat_completions()`
  - `backend/app/routers/v1_proxy/messages.py` — `messages_endpoint()`
  - `backend/app/routers/v1_proxy/responses.py` — `responses_endpoint()`
  - `backend/app/routers/v1_proxy/embeddings.py` — `embeddings()`
  - Adapter-style (not model-resolution based): `images.py`, `audio.py`
- **Duplication**: Shared skeleton remains:
  - `exclude_ids` / `refreshed_ids` / `last_error_*` → `while True` →
    `resolve_model_to_targets` → take `targets[0]`
  - `HTTPStatusError` → optional `_maybe_refresh_on_auth_error` →
    `_should_fallback_on_error` → `_mark_conn_failed` / exclude
  - `ConnectError` / bare `Exception` → exclude, continue
  - Final `JSONResponse` from `last_error_*`
- **Proposed DRY extraction**: `_run_target_fallback(...)` in
  `v1_proxy/shared.py` owning the loop + exception trio; callers supply
  per-target perform + error-envelope callbacks.
- **PS Rule check**: safe — generic proxy infrastructure.
- **Risk**: Medium-High — envelopes differ (messages Claude-style; chat 503
  no-cooldown; responses dual build paths). Diff per endpoint before extract.
- **Effort**: M
- **Confidence**: High

---

### [Priority: High] Streaming SSE byte-buffer + tracking tail duplicated

- **Locations**:
  - `routers/v1_proxy/shared.py` — `_stream_response().generate()`
  - `routers/v1_proxy/chat.py` — `_stream_claude_response`,
    `_stream_grok_responses`
  - `routers/v1_proxy/messages.py` — `_messages_stream_response` generators
  - `routers/v1_proxy/responses.py` — `_stream_responses`,
    `_stream_responses_passthrough`
- **Duplication**: Hand-rolled `aiter_bytes` / split-on-`\n` / flush buffer;
  post-stream `async_session` + `save_request_tracking` + `track_request_end`.
- **Proposed DRY extraction**:
  - `iter_sse_lines(resp)` in `shared.py`
  - `finalize_stream_tracking(...)` for the tracking tail
- **PS Rule check**: safe — buffering/tracking are generic; translators stay
  local.
- **Risk**: Medium — preserve byte fidelity and swallowed tracking errors.
- **Effort**: M
- **Confidence**: High

---

### [Priority: Medium] `save_request_usage` duplicates `save_request_tracking`

- **Locations**: `backend/app/services/usage_tracking.py`
- **Duplication**: ~90-line shared body (settings cost rates, `UsageHistory`,
  `UsageDaily` upsert). `save_request_usage` still has **no external callers**.
- **Proposed DRY extraction**: Delegate to `save_request_tracking`, or delete
  `save_request_usage` after confirming it is not a reserved public API.
- **PS Rule check**: safe.
- **Risk**: Low if deleted/delegated carefully; Medium if blindly merged
  (bodies have drifted — tracking has request-detail + SSE notify).
- **Effort**: S
- **Confidence**: High

---

### [Priority: Medium] Settings singleton `id == 1` fetch repeated

- **Locations**: `services/usage_tracking.py`, `services/proxy.py`
  (`get_provider_strategy`, `get_combo_strategy`), `routers/settings.py`,
  `routers/mitm.py`, `routers/auth.py`, `v1_proxy/models.py`, etc.
- **Duplication**: `select(SettingsModel).where(id == 1)` + `json.loads`.
- **Proposed DRY extraction**: `async def get_settings_blob(db) -> dict`
  (return a copy). Optionally share strategy-default parsing between
  `get_provider_strategy` / `get_combo_strategy`.
- **Overlap**: Closely related to `_get_or_create_*` below; one settings
  helper can cover read path for both.
- **PS Rule check**: safe.
- **Risk**: Low-Medium — callers that mutate the dict need a copy.
- **Effort**: S
- **Confidence**: High

---

### [Priority: Medium] `_get_or_create_*` singleton-row helpers

- **Locations**: `routers/settings.py` (`_get_or_create_settings`),
  `routers/mitm.py` (`_get_or_create_config`).
- **Duplication**: select id==1, create defaults if missing, flush/refresh.
- **Note**: Concurrent creates can hit unique-constraint races (seen on
  `/mitm/config` under double-fetch). Any shared helper should use a safe
  upsert / catch-IntegrityError-and-reselect pattern, not naive insert.
- **Proposed DRY extraction**:
  `async def get_or_create_singleton(db, model, defaults) -> model`.
- **PS Rule check**: safe.
- **Risk**: Low if race-safe; Medium if copied as-is.
- **Effort**: S
- **Confidence**: High

---

### [Priority: Medium] Provider `validate()` HTTP-error skeleton

- **Locations**: Many `providers/*/handler.py` overrides (~14 simple GET
  validators share the ConnectError / Timeout / Exception trio).
- **Proposed DRY extraction**: Helpers on `BaseProviderHandler` (e.g.
  `_validate_get`, shared status→`ValidateResult` mapping). Providers keep
  URL path and message strings.
- **PS Rule check**: safe — stays inside `app/providers/`.
- **Risk**: Medium — message wording differs per provider.
- **Effort**: M
- **Confidence**: High

---

### [Priority: Medium] `Provider(name)` try/except dispatch repeated

- **Locations**: `services/proxy.py`, `routers/v1_proxy/*`,
  `routers/providers/*`, `services/catalog.py`.
- **Duplication**:
  `try: Provider(name)... except (ValueError, ModuleNotFoundError)`.
- **Proposed DRY extraction**: `safe_handler(id)` / `safe_config(id)` on
  `providers/provider.py`; optional `_iter_provider_configs()` for the three
  alias-map builders in `proxy.py`.
- **PS Rule check**: safe — dispatch plumbing.
- **Risk**: Low-Medium — fallbacks differ slightly per call site.
- **Effort**: M
- **Confidence**: High

---

### [Priority: Medium] SSE OpenAI-style usage capture repeated

- **Locations**: `shared._stream_response`, `messages.py`, `chat.py`
  Claude/Grok streamers, `responses.py` `_handle_chat_sse_line`.
- **Duplication**: `data: ` line → `json.loads` → stash `usage`.
- **Proposed DRY extraction**: `_capture_openai_usage(line, current)` next to
  existing `_capture_qoder_usage` in `shared.py`.
- **PS Rule check**: safe.
- **Risk**: Low.
- **Effort**: S
- **Confidence**: High

---

### [Priority: Low] `map_tokens` core trio in OAuth handlers

- **Locations**: ~17 `providers/*/oauth.py` `map_tokens` methods.
- **Proposed DRY extraction** (optional): `_standard_tokens(tokens, extra)` on
  `BaseOAuthHandler` for access/refresh/expires only.
- **PS Rule check**: safe if helper stays in `oauth_base.py`.
- **Risk**: Medium — field names / expiry formats vary (e.g. Qoder).
- **Effort**: S
- **Confidence**: Medium — keep Low priority.

---

### [Priority: Low] `ProxyTarget` vs `ResolvedTarget` duplicate types

- **Locations**: `routers/v1_proxy/shared.py` (`ProxyTarget`) vs
  `services/proxy.py` (`ResolvedTarget`) — same fields.
- **Proposed DRY extraction**: Keep one type; alias/import the other.
- **PS Rule check**: safe.
- **Risk**: Low.
- **Effort**: S
- **Confidence**: High

---

## Top 5 recommended next extractions

1. **Streaming SSE reader + tracking tail** — high duplication, contained in
   `v1_proxy`, medium risk if done carefully.
2. **SSE OpenAI usage capture helper** — small, low risk, pairs with #1.
3. **`save_request_usage` delete or delegate** — dead duplicate; confirm then
   remove.
4. **Settings blob + race-safe singleton get-or-create** — covers settings /
   mitm / strategy readers.
5. **Proxy fallback loop** — highest impact but highest risk; do after the
   smaller v1_proxy helpers land.

## Explicit non-recommendations / dropped

- **Hardcoded Qoder refresh helpers in routers** — superseded by
  `handler.try_refresh_on_auth_error` (applied). Do not reintroduce
  `_try_qoder_*` / `_maybe_refresh_qoder_*` names in routers.
- **HTTPException `not_found()` wrappers / httpx client factories / timing
  decorators** (v1 report) — low value vs noise; skip unless a concrete bug
  needs them.
- **Full `map_tokens` merge across OAuth providers** — too much field drift;
  core-trio helper only if needed.

## Notes

- Line numbers in older drafts are stale; locate by symbol name.
- Applied helpers live in `backend/app/routers/v1_proxy/shared.py` and
  `backend/app/providers/base.py` / `qoder/handler.py`.
- No further behavior-changing refactors are proposed here — only mechanical
  extractions that preserve response shapes and DB writes.
