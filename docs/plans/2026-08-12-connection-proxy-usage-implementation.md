# Connection Proxy Usage Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Apply Proxy real — per-connection Off / Selective / All usage modes, pool default template + mass apply, and inject `httpx` proxy for the right outbound purposes.

**Architecture:** Store `proxyUsage` on connection `data` JSON; store `default_proxy_usage` on `proxy_pools`. Resolve with `resolve_outbound_proxy(conn, purpose, pool)` and open clients via `create_upstream_client`. Chat playground sends `X-9Router-Purpose: test-chat`; production `/v1/*` uses purpose `upstream` (proxy only when mode is `all`).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, httpx, React/Zustand pages.

**Spec:** `docs/plans/2026-08-12-connection-proxy-usage-design.md`

## Global Constraints

- Code/docs English; user chat Indonesian.
- No new columns on `provider_connections` — `proxyUsage` lives in `data` JSON.
- Alembic OK for `proxy_pools.default_proxy_usage` (JSONB/Text).
- Use `.venv-test` for pytest — never host `backend/.venv`.
- Do not auto-push; user tests first.
- Do not change Settings `outboundProxy*` in this plan.
- Do not build tool-calling checkers.
- Max 80 characters per Python/JS line where practical.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/outbound_proxy.py` | Parse usage, resolve URL, ContextVar, client factory |
| `backend/tests/test_outbound_proxy.py` | Unit tests for resolve / purpose / modes |
| `backend/alembic/versions/*_proxy_pool_default_usage.py` | Add `default_proxy_usage` |
| `backend/app/models/proxy_pool.py` | Column |
| `backend/app/schemas/proxy_pool.py` | Create/Update/Out + mass-apply response |
| `backend/app/routers/proxy_pools.py` | CRUD fields + mass-apply endpoint |
| `backend/app/routers/providers/testing.py` | Purpose `testConnection` + proxy |
| `backend/app/routers/providers/bulk_jobs.py` | Bulk test uses same path |
| `backend/app/providers/base.py` | `_validate_*` use `create_upstream_client` |
| `backend/app/routers/models.py` | `/models/test` purpose `testModel` |
| `backend/app/routers/v1_proxy/chat.py` (+ messages/shared as needed) | Purpose from header; client proxy |
| `backend/app/services/token_refresh.py` / oauth HTTP | Purpose `oauthRefresh` |
| `frontend/src/pages/ProviderDetailPage.jsx` | Usage UI + persist `proxyUsage` |
| `frontend/src/pages/ProxyPoolsPage.jsx` | Template UI + mass apply |
| `frontend/src/pages/ChatPage.jsx` | Send purpose header |
| `frontend/src/api/proxyPools.js` | Mass-apply API helper |

---

### Task 1: Outbound proxy resolver + client factory

**Files:**
- Create: `backend/app/services/outbound_proxy.py`
- Test: `backend/tests/test_outbound_proxy.py`

**Interfaces:**
- Produces:
  - `ProxyPurpose = Literal["testConnection","testModel","testChat","oauthRefresh","upstream"]`
  - `DEFAULT_PROXY_USAGE: dict` — `{mode:"off", flags:{...all false}}`
  - `parse_proxy_usage(data: dict | None) -> dict` — normalized usage
  - `purpose_from_header(value: str | None) -> ProxyPurpose` — `test-chat`→`testChat`; else `upstream`
  - `should_use_proxy(usage: dict, purpose: ProxyPurpose) -> bool`
  - `resolve_proxy_url(*, usage: dict, purpose: ProxyPurpose, pool: ProxyPool | None) -> str | None`  
    Raises `ProxyRequiredError` if need proxy and pool missing/inactive and `strict_proxy`
  - `create_upstream_client(*, proxy: str | None = None, timeout: float = 30.0, **kwargs) -> httpx.AsyncClient`
  - `use_outbound_proxy(proxy: str | None)` async context manager setting ContextVar so nested `create_upstream_client()` without explicit proxy inherits it

- [ ] **Step 1: Write failing tests**

```python
"""Unit tests for outbound proxy resolution."""

import pytest

from app.services.outbound_proxy import (
    DEFAULT_PROXY_USAGE,
    parse_proxy_usage,
    purpose_from_header,
    should_use_proxy,
    resolve_proxy_url,
    ProxyRequiredError,
)


def test_parse_missing_defaults_to_off():
    assert parse_proxy_usage(None)["mode"] == "off"
    assert parse_proxy_usage({}) == DEFAULT_PROXY_USAGE


def test_purpose_header_test_chat():
    assert purpose_from_header("test-chat") == "testChat"
    assert purpose_from_header(None) == "upstream"


def test_selective_test_connection_not_upstream():
    usage = {
        "mode": "selective",
        "flags": {
            "testConnection": True,
            "testModel": False,
            "testChat": False,
            "oauthRefresh": False,
        },
    }
    assert should_use_proxy(usage, "testConnection") is True
    assert should_use_proxy(usage, "upstream") is False


def test_all_uses_proxy_for_upstream():
    usage = {"mode": "all", "flags": dict(DEFAULT_PROXY_USAGE["flags"])}
    assert should_use_proxy(usage, "upstream") is True


class _Pool:
    def __init__(self, url, active=True, strict=False):
        self.proxy_url = url
        self.is_active = active
        self.strict_proxy = strict


def test_resolve_returns_url_when_needed():
    usage = {"mode": "all", "flags": dict(DEFAULT_PROXY_USAGE["flags"])}
    url = resolve_proxy_url(
        usage=usage, purpose="upstream", pool=_Pool("http://p:1")
    )
    assert url == "http://p:1"


def test_resolve_strict_raises_when_inactive():
    usage = {"mode": "all", "flags": dict(DEFAULT_PROXY_USAGE["flags"])}
    with pytest.raises(ProxyRequiredError):
        resolve_proxy_url(
            usage=usage,
            purpose="upstream",
            pool=_Pool("http://p:1", active=False, strict=True),
        )
```

- [ ] **Step 2: Run — expect FAIL (import)**

```bash
cd backend && PYTHONPATH=. ../.venv-test/bin/python -m pytest \
  tests/test_outbound_proxy.py -q
```

- [ ] **Step 3: Implement `outbound_proxy.py`** (~120 lines)

Keep resolution pure (no DB). `create_upstream_client` reads explicit `proxy=` or ContextVar.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/outbound_proxy.py \
  backend/tests/test_outbound_proxy.py
git commit -m "feat(proxy): outbound proxy usage resolver and client factory"
```

---

### Task 2: Pool `default_proxy_usage` + mass-apply API

**Files:**
- Create: Alembic revision under `backend/alembic/versions/`
- Modify: `backend/app/models/proxy_pool.py`
- Modify: `backend/app/schemas/proxy_pool.py`
- Modify: `backend/app/routers/proxy_pools.py`
- Test: `backend/tests/test_proxy_pool_usage.py` (mass-apply helper logic; DB optional)

**Interfaces:**
- Produces:
  - Column `default_proxy_usage` JSON/Text nullable on `proxy_pools`
  - Schema field `defaultProxyUsage: Optional[dict]` (camelCase out) / accept snake or camel on write — match existing pool schema style (`proxy_url` snake in API today → keep snake `default_proxy_usage` for consistency with `proxy_url`)
  - `POST /proxy-pools/{pool_id}/apply-usage` → `{ updated: N }`
  - Helper `apply_pool_usage_to_connections(db, pool) -> int` updates each `ProviderConnection` with that `proxy_pool_id`: merge `data["proxyUsage"] = parse_proxy_usage(pool.default_proxy_usage)`

- [ ] **Step 1: Migration**

Add nullable JSON column `default_proxy_usage` (PostgreSQL JSONB preferred).

- [ ] **Step 2: Model + schemas + CRUD wire**

Create/Update/Out include `default_proxy_usage`.

- [ ] **Step 3: Mass-apply endpoint**

Load pool; select connections where `proxy_pool_id == pool.id`; for each parse `conn.data` JSON, set `proxyUsage`, write back, commit; return count.

- [ ] **Step 4: Unit test** for merge helper (in-memory dicts / mock) without full DB if easier:

```python
def test_merge_proxy_usage_into_data():
    from app.services.outbound_proxy import merge_proxy_usage_into_data
    data = {"apiKey": "x"}
    usage = {"mode": "all", "flags": {
        "testConnection": False, "testModel": False,
        "testChat": False, "oauthRefresh": False,
    }}
    out = merge_proxy_usage_into_data(data, usage)
    assert out["apiKey"] == "x"
    assert out["proxyUsage"]["mode"] == "all"
```

Add `merge_proxy_usage_into_data` in `outbound_proxy.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/*.py backend/app/models/proxy_pool.py \
  backend/app/schemas/proxy_pool.py backend/app/routers/proxy_pools.py \
  backend/app/services/outbound_proxy.py backend/tests/test_proxy_pool_usage.py
git commit -m "feat(proxy-pools): default usage template and mass apply"
```

---

### Task 3: Wire connection test (+ base validate clients)

**Files:**
- Modify: `backend/app/routers/providers/testing.py`
- Modify: `backend/app/providers/base.py` (`_validate_openai_compatible`, anthropic, embedding)
- Modify: `backend/app/routers/providers/bulk_jobs.py` (test path already calls `_test_provider_connection`)
- Optionally: provider `handler.validate` overrides that construct `httpx.AsyncClient` — pass through ContextVar by wrapping test in `use_outbound_proxy` so overrides that still use raw `AsyncClient` **miss** proxy unless updated. Prefer: wrap test in ContextVar **and** change base helpers to `create_upstream_client`. For overrides, add a follow-up step: replace `httpx.AsyncClient(` with `create_upstream_client(` in validate methods (grep-driven).

**Interfaces:**
- Consumes: `parse_proxy_usage`, `resolve_proxy_url`, `use_outbound_proxy`, `create_upstream_client`
- `_test_provider_connection` loads pool if `conn.proxy_pool_id`, resolves for purpose `testConnection`, enters `use_outbound_proxy(url)`, then calls `handler.validate`

- [ ] **Step 1: Update base `_validate_*` to use `create_upstream_client(timeout=15.0)`** (inherits ContextVar)

- [ ] **Step 2: In `_test_provider_connection`**

```python
from app.models.proxy_pool import ProxyPool
from app.services.outbound_proxy import (
    parse_proxy_usage,
    resolve_proxy_url,
    use_outbound_proxy,
    ProxyRequiredError,
)

usage = parse_proxy_usage(data)
pool = None
if conn.proxy_pool_id:
    pool = (await db.execute(
        select(ProxyPool).where(ProxyPool.id == conn.proxy_pool_id)
    )).scalar_one_or_none()
try:
    proxy_url = resolve_proxy_url(
        usage=usage, purpose="testConnection", pool=pool
    )
except ProxyRequiredError as exc:
    return {"valid": False, "error": str(exc), "latencyMs": 0, "models": None}

async with use_outbound_proxy(proxy_url):
    result = await handler.validate(api_key, data)
```

- [ ] **Step 3: Grep provider handlers** — any `validate` that uses `httpx.AsyncClient` → switch to `create_upstream_client` (same kwargs). Skip OAuth-only modules in this task.

- [ ] **Step 4: Smoke import + existing bulk job tests**

```bash
cd backend && PYTHONPATH=. ../.venv-test/bin/python -m pytest \
  tests/test_outbound_proxy.py tests/test_bulk_jobs.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/providers/testing.py \
  backend/app/providers/base.py backend/app/providers/*/handler.py
git commit -m "feat(providers): connection test respects proxyUsage"
```

---

### Task 4: Wire `/models/test` + `/v1` chat (purpose header)

**Files:**
- Modify: `backend/app/routers/models.py` (test endpoint)
- Modify: `backend/app/routers/v1_proxy/chat.py`
- Modify: `backend/app/routers/v1_proxy/messages.py` (same pattern if it opens httpx)
- Modify: `frontend/src/pages/ChatPage.jsx` (header only)

**Interfaces:**
- Helper in `outbound_proxy.py` or small `v1_proxy` util:

```python
async def proxy_for_connection(
    db, conn: ProviderConnection | None, purpose: ProxyPurpose
) -> str | None:
    ...
```

- Chat: `purpose = purpose_from_header(request.headers.get("x-9router-purpose"))`
- Before each `httpx.AsyncClient` for a target with `connection_id`, load conn, resolve, `create_upstream_client(proxy=..., timeout=300)`

- [ ] **Step 1: models test** — resolve purpose `testModel` for the connection used by the model test

- [ ] **Step 2: chat.py** — replace `httpx.AsyncClient(timeout=300.0)` sites that forward upstream with factory + resolved proxy for that target connection

- [ ] **Step 3: ChatPage.jsx**

```javascript
headers: {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${token || ''}`,
  'X-9Router-Purpose': 'test-chat',
},
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/models.py \
  backend/app/routers/v1_proxy/chat.py \
  backend/app/routers/v1_proxy/messages.py \
  frontend/src/pages/ChatPage.jsx
git commit -m "feat(proxy): models test and chat purpose-aware outbound proxy"
```

---

### Task 5: Wire OAuth refresh purpose

**Files:**
- Modify: `backend/app/services/token_refresh.py`
- Modify: paths in `backend/app/services/oauth.py` / provider oauth that take connection context when refreshing a known connection

**Interfaces:**
- For each connection being refreshed: parse usage, resolve `oauthRefresh`, wrap HTTP with `use_outbound_proxy`

- [ ] **Step 1: token_refresh loop** — before `refresh_access_token`, resolve proxy for that conn and set ContextVar for the call duration

- [ ] **Step 2: Ensure oauth HTTP helpers use `create_upstream_client` OR ContextVar-aware client** — if they use raw `httpx.AsyncClient`, switch those call sites used by refresh to `create_upstream_client`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/token_refresh.py \
  backend/app/services/oauth.py
git commit -m "feat(proxy): OAuth refresh respects proxyUsage oauthRefresh flag"
```

---

### Task 6: Frontend — ProviderDetailPage usage UI

**Files:**
- Modify: `frontend/src/pages/ProviderDetailPage.jsx`
- Ensure `proxyUsage` round-trips via update/create payloads (`data` merge on backend already stores unknown keys in JSON — confirm update path writes `proxyUsage` into `data` blob)

**Backend check:** `connections.py` update must accept `proxyUsage` in body and merge into `data` (add field on update schema if missing).

**Files (backend if needed):**
- Modify: `backend/app/schemas/provider.py` — optional `proxyUsage: Optional[dict]`
- Modify: `backend/app/routers/providers/connections.py` — merge into data
- Modify: `backend/app/routers/providers/helpers.py` — expose `proxyUsage` in client serialization

- [ ] **Step 1: API persist `proxyUsage` on create/update + include in connection list payload**

- [ ] **Step 2: UI** — near proxy pool select: radio Off / Selective / All; Selective shows four checkboxes; save with connection update / Apply Proxy

- [ ] **Step 3: When assigning pool from pool template** — if connection has no usage yet, copy `default_proxy_usage` from selected pool (client-side from pools list)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProviderDetailPage.jsx \
  backend/app/schemas/provider.py \
  backend/app/routers/providers/connections.py \
  backend/app/routers/providers/helpers.py
git commit -m "feat(providers): UI and API for connection proxyUsage modes"
```

---

### Task 7: Frontend — ProxyPoolsPage template + mass apply

**Files:**
- Modify: `frontend/src/pages/ProxyPoolsPage.jsx`
- Modify: `frontend/src/api/proxyPools.js`

- [ ] **Step 1: API**

```javascript
applyUsage: (id) => client.post(`/proxy-pools/${id}/apply-usage`),
```

- [ ] **Step 2: Form fields** for `default_proxy_usage` (same Off/Selective/All + flags)

- [ ] **Step 3: Button** “Apply usage settings to all connections using this pool” with confirm; toast result `updated`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProxyPoolsPage.jsx frontend/src/api/proxyPools.js
git commit -m "feat(proxy-pools): default usage UI and mass apply action"
```

---

### Task 8: Remaining `/v1/*` upstream clients (mode All)

**Files:**
- Modify: `backend/app/routers/v1_proxy/shared.py`, `responses.py`, `embeddings.py`, and other modules that open `httpx.AsyncClient` for connection-bound upstream

**Approach:** Add shared helper used by chat already; apply same resolve+factory pattern. Purpose always `upstream` (no header). Skip if no `connection_id`.

- [ ] **Step 1: Grep** `httpx.AsyncClient` under `v1_proxy/` and wire connection-bound forwards

- [ ] **Step 2: Focused pytest** still green; manual note in commit body

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/v1_proxy/
git commit -m "feat(proxy): apply outbound proxy to remaining v1 upstream clients"
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| `proxyUsage` on connection data | 1, 6 |
| Pool default template + mass apply | 2, 7 |
| Off / Selective / All + flags | 1, 6, 7 |
| testConnection uses proxy | 3 |
| testModel | 4 |
| testChat header | 4 |
| oauthRefresh | 5 |
| upstream only when All | 4, 8 |
| strict_proxy fail | 1, 3 |
| No provider new columns | all |
| No tool-calling checker | — |

## Consistency notes

- Header name: `X-9Router-Purpose: test-chat` (value kebab; purpose id camelCase).
- Pool API keeps snake_case fields like existing `proxy_url`.
- ContextVar ensures validate overrides pick up proxy only after they use `create_upstream_client`; Task 3 grep replacement is mandatory for correctness on custom validators.
- Bulk test already calls `_test_provider_connection` — no separate bulk proxy logic.
