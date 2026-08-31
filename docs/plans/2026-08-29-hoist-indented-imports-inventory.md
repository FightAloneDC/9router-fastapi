# Inventory: Hoist Indented Imports — 2026-08-29

**Status:** in progress (2026-09-01: quota.py + P0 + P1
hoisted; documented cycles remain in `base.py` / `proxy.py` /
`connection_health.py`)

**Rule:** In production code under `backend/app/`, `import` /
`from … import` must live at **module top level**. Imports inside
`def` / `if` / `try` / other indented blocks are not acceptable
style, except:

- `if TYPE_CHECKING:` (type-only imports)
- Rare, documented circular-import workarounds (prefer fixing the
  cycle instead)

**Exempt:** `backend/tests/` (lazy imports remain acceptable).

**Detection regex** (run from repo root):

```bash
rg -c --glob '*.py' '^\s+(from|import)\s+' backend/app | sort -t: -k2 -nr
```

**Snapshot:** 2026-09-01 re-scan — **58 files** remain
(was 82 on 2026-08-29; 69 after quota.py; 65 after P0). Match
counts below.
Re-run the command after each batch; uncheck rows as they go
clean (count → 0, or only `TYPE_CHECKING` / documented exceptions
remain).

**Suggested fix order:**

1. P0 — entrypoint + hot paths (`main`, `v1_proxy`, `proxy`)
2. P1 — shared services / routers
3. P2 — provider handlers & quota (many similar patterns)
4. P3 — single-match leftovers

**Per-file verify:** hoist → `import app.main` (or module smoke) →
relevant pytest green. Watch for new circular imports.

---

## P0 — High traffic (≥9 matches)

| Done | Matches | Path |
|------|--------:|------|
| [x] | 0 | `backend/app/routers/v1_proxy/chat.py` |
| [x] | 1 | `backend/app/services/proxy.py` |
| [x] | 0 | `backend/app/providers/qoder/handler.py` |
| [x] | 0 | `backend/app/providers/qoder/auth.py` |
| [x] | 0 | `backend/app/providers/openrouter/quota.py` |
| [x] | 0 | `backend/app/routers/v1_proxy/models.py` |
| [x] | 2 | `backend/app/providers/base.py` |

## P1 — Medium (5–8 matches)

| Done | Matches | Path |
|------|--------:|------|
| [x] | 3 | `backend/app/services/connection_health.py` |
| [x] | 0 | `backend/app/routers/providers/connections.py` |
| [x] | 0 | `backend/app/providers/grok_cli/quota.py` |
| [x] | 0 | `backend/app/providers/cohere/quota.py` |
| [x] | 0 | `backend/app/providers/cerebras/quota.py` |
| [x] | 0 | `backend/app/routers/v1_proxy/messages.py` |
| [x] | 0 | `backend/app/routers/providers/validation.py` |
| [x] | 0 | `backend/app/providers/nvidia/quota.py` |
| [x] | 0 | `backend/app/providers/mistral/quota.py` |
| [x] | 0 | `backend/app/providers/deepseek/quota.py` |
| [x] | 0 | `backend/app/routers/v1_proxy/audio.py` |
| [x] | 0 | `backend/app/routers/providers/testing.py` |
| [x] | 0 | `backend/app/providers/grok_cli/handler.py` |
| [x] | 0 | `backend/app/main.py` |

## P2 — Low–medium (2–4 matches)

| Done | Matches | Path |
|------|--------:|------|
| [ ] | 4 | `backend/app/services/provider_aliases.py` |
| [ ] | 4 | `backend/app/routers/providers/models.py` |
| [x] | 0 | `backend/app/providers/alims_intl/quota.py` |
| [ ] | 3 | `backend/app/services/oauth.py` |
| [ ] | 3 | `backend/app/services/oauth_providers.py` |
| [ ] | 3 | `backend/app/routers/v1_proxy/responses.py` |
| [ ] | 3 | `backend/app/routers/quota.py` |
| [ ] | 3 | `backend/app/routers/providers/nodes.py` |
| [x] | 0 | `backend/app/providers/voyage_ai/quota.py` |
| [ ] | 3 | `backend/app/providers/qoder/oauth.py` |
| [x] | 0 | `backend/app/providers/morph/quota.py` |
| [ ] | 3 | `backend/app/providers/mimo_free/handler.py` |
| [x] | 0 | `backend/app/providers/jina_ai/quota.py` |
| [x] | 0 | `backend/app/providers/groq/quota.py` |
| [x] | 0 | `backend/app/providers/commandcode/quota.py` |
| [ ] | 2 | `backend/app/services/usage_tracking.py` |
| [ ] | 2 | `backend/app/services/catalog.py` |
| [ ] | 2 | `backend/app/routers/oauth.py` |
| [ ] | 2 | `backend/app/providers/xiaomi_tokenplan/handler.py` |
| [ ] | 2 | `backend/app/providers/provider.py` |
| [ ] | 2 | `backend/app/providers/jina_ai/handler.py` |
| [ ] | 2 | `backend/app/providers/gemini/handler.py` |
| [ ] | 2 | `backend/app/providers/anthropic/handler.py` |

## P3 — Single match (1)

| Done | Matches | Path |
|------|--------:|------|
| [ ] | 1 | `backend/app/services/voice_fetchers.py` |
| [ ] | 1 | `backend/app/services/token_refresh.py` |
| [ ] | 1 | `backend/app/services/search_adapters.py` |
| [ ] | 1 | `backend/app/services/rerank_adapters.py` |
| [ ] | 1 | `backend/app/services/quota/__init__.py` |
| [ ] | 1 | `backend/app/services/provider_models_store.py` |
| [ ] | 1 | `backend/app/services/api_key_auth.py` |
| [ ] | 1 | `backend/app/services/active_requests.py` |
| [ ] | 1 | `backend/app/routers/usage.py` |
| [ ] | 1 | `backend/app/routers/settings.py` |
| [ ] | 1 | `backend/app/routers/providers/helpers.py` |
| [ ] | 1 | `backend/app/routers/auth.py` |
| [ ] | 1 | `backend/app/providers/youcom/handler.py` |
| [ ] | 1 | `backend/app/providers/voyage_ai/handler.py` |
| [ ] | 1 | `backend/app/providers/tavily/handler.py` |
| [ ] | 1 | `backend/app/providers/serper/handler.py` |
| [ ] | 1 | `backend/app/providers/searxng/handler.py` |
| [ ] | 1 | `backend/app/providers/searchapi/handler.py` |
| [ ] | 1 | `backend/app/providers/perplexity/handler.py` |
| [ ] | 1 | `backend/app/providers/openrouter/handler.py` |
| [ ] | 1 | `backend/app/providers/opencode/handler.py` |
| [ ] | 1 | `backend/app/providers/mistral/transform.py` |
| [ ] | 1 | `backend/app/providers/mistral/handler.py` |
| [ ] | 1 | `backend/app/providers/linkup/handler.py` |
| [ ] | 1 | `backend/app/providers/keelcode/handler.py` |
| [ ] | 1 | `backend/app/providers/inworld/handler.py` |
| [ ] | 1 | `backend/app/providers/__init__.py` |
| [ ] | 1 | `backend/app/providers/grok_cli/transform.py` |
| [ ] | 1 | `backend/app/providers/grok_cli/quality_gate.py` |
| [ ] | 1 | `backend/app/providers/grok_cli/debug_dump.py` |
| [ ] | 1 | `backend/app/providers/grok_cli/anomaly.py` |
| [ ] | 1 | `backend/app/providers/google_pse/handler.py` |
| [ ] | 1 | `backend/app/providers/exa/handler.py` |
| [ ] | 1 | `backend/app/providers/edge_tts/handler.py` |
| [ ] | 1 | `backend/app/providers/codex/proxy.py` |
| [ ] | 1 | `backend/app/providers/brave/handler.py` |
| [ ] | 1 | `backend/app/providers/alims_intl/handler.py` |
| [ ] | 1 | `backend/app/middleware/request_logging.py` |

---

## Blocked (documented circular imports)

Keep these indented; splitting the module is the real fix.

- `backend/app/providers/base.py`
  - `model_helpers` imports `BaseProviderConfig` from this module
  - `routers.providers.constants` loads package `__init__` →
    `Provider` → this module
- `backend/app/services/proxy.py`
  - `provider_models_store` → `routers.providers` →
    `invalidate_connection_cache` on this module
- `backend/app/services/connection_health.py`
  - `proxy.py` imports this module at top level
    (`_resolve_base_url`, `build_clear_cooldown_update`,
    `invalidate_connection_cache`)

---

## Notes for implementers

- Do not expand scope (no drive-by refactors).
- Prefer one batch area at a time (e.g. all `quota.py` with the
  same SQLAlchemy lazy pattern).
- If hoist causes `ImportError` / circular import: stop, document
  the cycle in this file under **Blocked**, then either split the
  module or keep a minimal indented import with a one-line why.
- Update match counts when re-scanning; mark **Done** only when
  the file is clean under the rule above.
- 2026-08-31: hoisted SQLAlchemy / session / model imports in
  all `providers/*/quota.py`. `services/quota/__init__.py` stays
  indented (discovers `app.providers`).
- Tests are exempt. Do not retarget test patches. If a hoist
  would bind a name that tests patch on the source module, import
  the module at top level and look up the attribute at call time
  (`database.async_session()`, `qoder_auth.fetch_user_info()`).
- 2026-08-31 P0: hoisted `v1_proxy/chat.py`, `v1_proxy/models.py`,
  `qoder/handler.py`, `qoder/auth.py`; `proxy.py` / `base.py`
  keep the cycles above.
- 2026-09-01 P1: hoisted remaining P1 table rows in document
  order. `connection_health.py` keeps the proxy cycle above.
