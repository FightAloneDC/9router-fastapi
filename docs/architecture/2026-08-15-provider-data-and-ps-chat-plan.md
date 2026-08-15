# Provider catalog + PS chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `provider_models` the only catalog, keep quota and
chat transforms provider-specific, and add a native Google
generateContent client door.

**Architecture:** Catalog is one table per provider id. Connections
stay accounts (JSON blob for credentials/health, not model lists).
`quota_cache.quotas` stays opaque JSON. `/v1` chat/messages/responses
stay; a sibling `/v1beta` router accepts Google native generateContent
and forwards via the Gemini (and later gemini-cli / antigravity)
handler. Routers do not grow `if provider ==` lists.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic autogenerate from
models, httpx, pytest.

## Global Constraints

- Code and docs: English. Chat with the user: Indonesian.
- No new columns on `provider_connections`. Provider extras stay in
  `data` JSON.
- Alembic: change the SQLAlchemy model first, then
  `uv run alembic revision --autogenerate`. Review the file. Data
  backfill (if any) is hand-edited into that revision. Then
  `upgrade head`.
- PS rule: quota meaning and request/response shape live in
  `backend/app/providers/<id>/`. No shared list of “per-model-limit
  providers”.
- Do not generalize quota semantics. Do not add
  `connection_model_quotas`.
- Do not turn on quality-gate 407 or phantom-write retry.
- Do not commit unless the user explicitly asks.
- Tests: `cd backend && ../.venv-local/bin/pytest …` if that venv
  exists, else `./.venv/bin/python -m pytest …`.
- Max 80 characters per Python/JS line.

## File map

| File | Role |
|------|------|
| `backend/app/models/provider_model.py` | Catalog ORM |
| `backend/app/models/__init__.py` | Must import `ProviderModel` for Alembic |
| `backend/app/services/provider_models_store.py` | Catalog CRUD |
| `backend/app/routers/providers/models.py` | Fetch/Clear → store only |
| `backend/app/routers/providers/connections.py` | Stop writing catalog onto every connection |
| `backend/app/routers/v1_proxy/models.py` | `/v1/models` from catalog |
| `backend/app/services/proxy.py` | Resolve connections via catalog, not `data.models` |
| `backend/app/routers/v1_proxy/google.py` | Native Google client door |
| `backend/app/routers/v1_proxy/router.py` | Keep `/v1` mounts only |
| `backend/app/main.py` | Mount `/v1beta` google router |
| `backend/app/providers/gemini/handler.py` | Outbound generateContent URL (already) |
| `backend/tests/test_provider_models_store.py` | Catalog unit tests |
| `backend/tests/test_google_native_proxy.py` | Native door tests |

---

### Task 1: Catalog store tests + behavior

**Files:**
- Create: `backend/tests/test_provider_models_store.py`
- Modify if needed: `backend/app/services/provider_models_store.py`
- Existing model: `backend/app/models/provider_model.py`

**Interfaces:**
- Consumes: `ProviderModel(provider, model_id, type, name, enabled)`
- Produces: `replace_provider_models`, `list_provider_models`,
  `list_disabled_ids`, `clear_provider_models`, `set_models_enabled`,
  `enable_all_models` as they exist in
  `provider_models_store.py` today

- [ ] **Step 1: Write failing/lock tests** (SQLite or the project’s
  existing async test DB pattern). Cover:

```python
import pytest
from app.services.provider_models_store import (
    replace_provider_models,
    list_provider_models,
    list_disabled_ids,
    set_models_enabled,
    clear_provider_models,
)


@pytest.mark.asyncio
async def test_replace_preserves_disabled(db):
    await replace_provider_models(
        db, "mistral",
        [{"id": "mistral-small-latest", "type": "llm"}],
    )
    await set_models_enabled(
        db, "mistral", ["mistral-small-latest"], False,
    )
    await replace_provider_models(
        db, "mistral",
        [{"id": "mistral-small-latest", "type": "llm"}],
        force_enable=False,
    )
    assert await list_disabled_ids(db, "mistral") == [
        "mistral-small-latest",
    ]


@pytest.mark.asyncio
async def test_replace_force_enable(db):
    await replace_provider_models(
        db, "mistral",
        [{"id": "a", "type": "llm"}],
    )
    await set_models_enabled(db, "mistral", ["a"], False)
    await replace_provider_models(
        db, "mistral",
        [{"id": "a", "type": "llm"}],
        force_enable=True,
    )
    assert await list_disabled_ids(db, "mistral") == []


@pytest.mark.asyncio
async def test_clear_is_provider_scoped(db):
    await replace_provider_models(
        db, "mistral", [{"id": "a", "type": "llm"}],
    )
    await replace_provider_models(
        db, "grok-cli", [{"id": "grok-4.6", "type": "llm"}],
    )
    n = await clear_provider_models(db, "mistral")
    assert n >= 1
    ids = [m["id"] for m in await list_provider_models(db, "grok-cli")]
    assert ids == ["grok-4.6"]
```

Use the same `db` fixture other backend tests use. If none exists,
use `AsyncSession` against the test engine already imported in
`backend/tests/test_provider_models.py` (that file is fetch-parser
tests; do not overload it).

- [ ] **Step 2: Run tests**

```bash
cd backend && ../.venv-local/bin/pytest \
  tests/test_provider_models_store.py -v
```

Expected: fail only if store/table missing; pass if store already
matches.

- [ ] **Step 3: Align store only if tests fail**

Do not add features. Preserve `force_enable` and disabled flags.

- [ ] **Step 4: Re-run tests — expect PASS**

---

### Task 2: Alembic from the model

**Files:**
- `backend/app/models/provider_model.py`
- `backend/app/models/__init__.py` (must import `ProviderModel`)
- New revision under `backend/alembic/versions/` via autogenerate

**Interfaces:**
- Produces: `provider_models` table matching the ORM:
  `id` UUID PK, `provider` String(100), `model_id` String(255),
  `type` String(50) default `llm`, `name` optional,
  `enabled` bool default true, timestamps, unique
  `(provider, model_id)`.

- [ ] **Step 1: Confirm `ProviderModel` is imported in
  `app.models.__init__`** so `Base.metadata` includes it.

- [ ] **Step 2: Autogenerate**

```bash
cd backend && uv run alembic revision --autogenerate -m "provider_models"
```

- [ ] **Step 3: Review the revision**

Keep `create_table` / unique constraint. If the table already exists
in the target DB, Alembic may emit empty or `create_table` — do not
apply a second create. If this is a fresh table, add a **data**
backfill (not schema) after `upgrade()` create:

```python
# After op.create_table(...): copy distinct model ids from
# connection JSON arrays into provider_models.
# Do not delete data.models here.
```

Use the same JSON unpack idea: `jsonb_array_elements` on
`provider_connections.data -> 'models'`, `GROUP BY provider,
model_id`, `ON CONFLICT DO NOTHING`.

- [ ] **Step 4: Upgrade**

```bash
cd backend && uv run alembic upgrade head
```

Verify: `\d provider_models` in psql or
`SELECT count(*) FROM provider_models`.

---

### Task 3: Fetch/Clear write catalog only

**Files:**
- Modify: `backend/app/routers/providers/models.py`
- Modify: `backend/app/routers/providers/connections.py`
  (create/test paths that assign `data["models"]`)
- Modify: `backend/app/routers/providers/bulk_jobs.py` if it still
  sets `data["models"]`
- Test: `backend/tests/test_provider_models_store.py` or a thin
  router test if the project already tests fetch with TestClient

**Interfaces:**
- Fetch: `replace_provider_models(db, provider, stored,
  force_enable=config.SYNC_DISABLED_WITH_MODEL_LIST)`
- Clear: `clear_provider_models(db, provider)` — provider grain, not
  one connection
- Must **not** assign `data["models"] = …` on fetch/clear

- [ ] **Step 1: Grep for remaining catalog writes**

```bash
rg 'data\["models"\]' backend/app
```

Allowed leftovers: combo models, unrelated JSON. Not fetch/clear.

- [ ] **Step 2: Change fetch/clear** so they only call the store.
  Clear docstring must not mention `settings.disabledModels` as the
  preserve path; disabled flags live on `provider_models.enabled`.

- [ ] **Step 3: Create/test connection** may still copy a model list
  into the blob **only if** some UI still reads it this week. Prefer
  writing the store and leaving `data.models` untouched (stale OK).
  Do not dual-write.

- [ ] **Step 4: Run store tests + any provider models router tests**

```bash
cd backend && ../.venv-local/bin/pytest \
  tests/test_provider_models_store.py -v
```

---

### Task 4: Proxy resolve + `/v1/models` from catalog

**Files:**
- Modify: `backend/app/services/proxy.py` (`_connection_has_model`
  call around the loop that reads `data.get("models", [])`)
- Modify: `backend/app/routers/v1_proxy/models.py`
  (`_get_disabled_models` already reads `provider_models`; drop the
  `settings.disabledModels` fallback once catalog rows exist)
- Test: add `backend/tests/test_proxy_catalog_models.py`

**Interfaces:**
- Helper (put in `provider_models_store.py` or `proxy.py`):

```python
async def provider_enabled_model_ids(
    db: AsyncSession, provider: str,
) -> set[str]:
    """Enabled catalog ids for this provider. Empty = none enabled."""
```

Bare model resolve: a connection matches if `provider` has that
`model_id` enabled in the catalog (not if the blob lists it).
Aliased `gcli/grok-4.6` already goes through
`_build_target_for_provider`; that path must not require the blob
list either — only active connections for that provider + catalog
enabled.

- [ ] **Step 1: Failing test** — connection blob has no `models` key,
  catalog has `grok-4.6` enabled, resolve `gcli/grok-4.6` (mock db or
  unit the matcher).

```python
def test_connection_matches_catalog_not_blob():
    catalog = {"grok-4.6"}
    blob_models: list = []
    assert "grok-4.6" in catalog
    assert blob_models == []
```

Then a real async test if the suite has db fixtures: insert
connection + catalog row, call `resolve_proxy_target`.

- [ ] **Step 2: Implement matcher using catalog ids loaded once per
  request** (map `provider -> set[str]`), not per-connection JSON.

- [ ] **Step 3: `/v1/models` lists `alias/model_id` from
  `provider_models` where `enabled` and provider has an active
  connection. Skip disabled. Do not union `data.models`.

- [ ] **Step 4: pytest the new file — PASS**

---

### Task 5: Native Google client door

**Files:**
- Create: `backend/app/routers/v1_proxy/google.py`
- Modify: `backend/app/main.py` — include router prefix `/v1beta`
- Do **not** hang this on `v1_proxy/router.py` (that is prefix `/v1`)
- Create: `backend/tests/test_google_native_proxy.py`
- Reuse: `GeminiHandler.build_upstream_url`

**Interfaces:**
- Client: `POST /v1beta/models/{model}:generateContent`
- Client: `POST /v1beta/models/{model}:streamGenerateContent`
- Body: Google JSON (`contents`, `generationConfig`, …) passed
  through. Do not convert from OpenAI.
- Resolve `model` the same way as chat (`gemini/gemini-2.0-flash` or
  bare id via catalog).
- Upstream: existing `build_upstream_url(..., stream=..., model=...)`
  plus `?key=` from `AUTH_QUERY_PARAM`.
- Log via existing usage helpers if chat.py already has a small
  shared function; otherwise call the same `save_request_*` used by
  chat. Do not copy grok/claude stream translators.

Starlette path: register explicit routes (colon is part of the path):

```python
from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/models/{model}:generateContent")
async def generate_content(model: str, request: Request):
    ...


@router.post("/models/{model}:streamGenerateContent")
async def stream_generate_content(model: str, request: Request):
    ...
```

Mount:

```python
# main.py
from app.routers.v1_proxy import google as google_native
app.include_router(
    google_native.router,
    prefix="/v1beta",
    tags=["v1beta-google"],
)
```

- [ ] **Step 1: Unit test URL builder** (already on handler):

```python
from app.providers.gemini.handler import GeminiHandler
from app.providers.gemini.config import GeminiConfig


def test_gemini_generate_content_url():
    h = GeminiHandler(GeminiConfig())
    url = h.build_upstream_url(
        "https://generativelanguage.googleapis.com/v1beta",
        stream=False,
        model="gemini-2.0-flash",
    )
    assert url.endswith(
        "/models/gemini-2.0-flash:generateContent"
    )
    surl = h.build_upstream_url(
        "https://generativelanguage.googleapis.com/v1beta",
        stream=True,
        model="gemini-2.0-flash",
    )
    assert "streamGenerateContent" in surl
```

- [ ] **Step 2: TestClient route exists** (may 401 without key):

```python
def test_v1beta_route_registered(client):
    r = client.post(
        "/v1beta/models/gemini-2.0-flash:generateContent",
        json={"contents": [{"parts": [{"text": "hi"}]}]},
    )
    assert r.status_code != 404
```

- [ ] **Step 3: Implement `google.py`** — auth like other v1
  endpoints (`validate_api_key`), resolve target, `handler.build_headers`
  / query key, POST body as client sent it, return upstream JSON.
  Stream: proxy SSE bytes; do not translate to OpenAI chunks.

- [ ] **Step 4: pytest both tests — PASS**

- [ ] **Step 5: Manual** (optional, needs a Gemini connection):

```bash
curl -sS -X POST \
  "$BASE/v1beta/models/gemini-2.0-flash:generateContent" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Reply with pong only"}]}]}'
```

Expected: Google-shaped JSON, not `choices[0].message`.

---

### Task 6: Quota — no shared semantics change

**Files:** none required unless a router already branches on
Alibaba/Antigravity by name.

- [ ] **Step 1:** `rg 'antigravity|alibaba' backend/app/services/quota
  backend/app/routers/quota.py`

- [ ] **Step 2:** If a shared module lists those providers, remove
  the list. Per-model vs per-account stays in
  `providers/<id>/quota.py`. `QuotaItem.model_id` remains optional.

- [ ] **Step 3:** Do not add tables.

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| `provider_models` catalog | 1–2 |
| Fetch/Clear/Disable on catalog | 3 |
| Blob not catalog SoT | 3–4 |
| Proxy / `/v1/models` from catalog | 4 |
| Opaque `quota_cache` | 6 |
| Four client doors; Google native | 5 |
| PS transforms (Mistral etc.) | unchanged; do not move into routers |
| No new connection columns | all tasks |
| Alembic from models | 2 |

## Out of scope (do not do in this plan)

- Quality gate / phantom write
- Extra client doors (Bedrock native, etc.)
- Rewriting all `if is_claude` / grok stream branches in `chat.py`
- Deleting stale `data.models` keys from existing rows (optional
  later cleanup)
