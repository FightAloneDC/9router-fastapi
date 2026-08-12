# Provider Connection Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add server-side search and multi-dimension filters to the paginated connection list on `/providers/:id`, with `total` (filtered) and `total_all` (unfiltered).

**Architecture:** Extend `GET /providers/by-provider/{id}/connections` with optional AND filters built by one shared SQL predicate helper. Frontend passes filter state into the existing `getProviderConnections` call, resets page on filter change, and updates footer/select-all copy.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL JSONB casts on `provider_connections.data` (TEXT JSON), React 19, Vite.

**Spec:** `docs/plans/2026-08-12-provider-connection-filters-design.md`

## Global Constraints

- Code/docs English; chat with user Indonesian (agents).
- No new DB columns — filter JSON fields via cast to JSONB.
- Filters combine with **AND**.
- Search `q` only on `name`, `email`, `displayName` (not id).
- `connectionIds` / select-all use the **same** filter as `items`.
- `total` = filtered count; `total_all` = provider count without list filters.
- `include_models` union stays **all connections for the provider** (not filtered) so the Models panel does not shrink when filtering accounts.
- Use host `.venv-test` or `.venv-local` for pytest — never `backend/.venv` from the host.
- Max 80 chars per line for Python/JS where practical; surgical diffs only.
- Do not auto-commit unless the user asks (plan commit steps are for the implementing agent when user requested commits / execution mode allows).

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/routers/providers/connection_filters.py` | Build SQLAlchemy `WHERE` clauses from filter params |
| `backend/app/routers/providers/connections.py` | Wire filters into list endpoint; return `total_all` |
| `backend/tests/test_connection_filters.py` | Unit tests for predicate builder (+ light list behavior if practical) |
| `frontend/src/pages/ProviderDetailPage.jsx` | Filter bar UI, state, debounce, footer, empty states |
| `frontend/src/api/providers.js` | No API shape change required (`params` already passed through) |

---

### Task 1: Connection filter predicate helper

**Files:**
- Create: `backend/app/routers/providers/connection_filters.py`
- Test: `backend/tests/test_connection_filters.py`

**Interfaces:**
- Produces:
  - `ConnectionListFilters` dataclass (or TypedDict) with optional fields: `q`, `is_active`, `test_status`, `auth_type`, `has_proxy`, `proxy_pool_id`, `token_issue`, `in_cooldown`
  - `build_connection_filter_clause(provider_id: str, filters: ConnectionListFilters) -> ColumnElement[bool]` — always includes `ProviderConnection.provider == provider_id`, then AND optional predicates
  - `CONNECTED_TEST_STATUSES: frozenset[str]` = `{"connected", "success", "active"}` for alias expansion when `test_status` is one of those

- [ ] **Step 1: Write failing tests for clause builder**

Create `backend/tests/test_connection_filters.py`:

```python
"""Unit tests for connection list filter predicates."""

from sqlalchemy import select

from app.models.provider import ProviderConnection
from app.routers.providers.connection_filters import (
    CONNECTED_TEST_STATUSES,
    ConnectionListFilters,
    build_connection_filter_clause,
)


def test_connected_aliases_constant():
    assert "connected" in CONNECTED_TEST_STATUSES
    assert "success" in CONNECTED_TEST_STATUSES
    assert "active" in CONNECTED_TEST_STATUSES


def test_base_clause_always_filters_provider():
    clause = build_connection_filter_clause(
        "qoder", ConnectionListFilters(),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "qoder" in sql


def test_q_adds_ilike_on_name_email_displayname():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(q="  alice@x.com  "),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "alice@x.com" in sql
    assert "ilike" in sql


def test_is_active_and_auth_type():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(is_active=False, auth_type="oauth"),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "is_active" in sql
    assert "oauth" in sql


def test_test_status_connected_expands_aliases():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(test_status="connected"),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "connected" in sql
    assert "success" in sql or "active" in sql


def test_has_proxy_true_and_false():
    for has_proxy in (True, False):
        clause = build_connection_filter_clause(
            "qoder",
            ConnectionListFilters(has_proxy=has_proxy),
        )
        sql = str(
            select(ProviderConnection).where(clause).compile(
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
        assert "proxy_pool_id" in sql


def test_token_issue_and_cooldown_reference_json():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(
            token_issue="any",
            in_cooldown=True,
        ),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "expiresat" in sql.replace("_", "") or "expires" in sql
    assert "modellock" in sql.replace("_", "") or "model_lock" in sql or "modellock" in sql
```

- [ ] **Step 2: Run tests — expect import/fail**

Run:

```bash
cd backend && PYTHONPATH=. ../.venv-test/bin/python -m pytest \
  tests/test_connection_filters.py -q
```

Expected: FAIL (module missing).

- [ ] **Step 3: Implement `connection_filters.py`**

```python
"""SQL predicates for paginated provider connection filters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import String, and_, cast, exists, false, func, literal, or_, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.expression import text

from app.models.provider import ProviderConnection

CONNECTED_TEST_STATUSES: frozenset[str] = frozenset(
    {"connected", "success", "active"}
)

TokenIssue = Literal["expired", "refresh_error", "any"]


@dataclass(frozen=True)
class ConnectionListFilters:
    q: str | None = None
    is_active: bool | None = None
    test_status: str | None = None
    auth_type: str | None = None
    has_proxy: bool | None = None
    proxy_pool_id: UUID | str | None = None
    token_issue: TokenIssue | None = None
    in_cooldown: bool | None = None


def _data_jsonb():
    return cast(ProviderConnection.data, JSONB)


def build_connection_filter_clause(
    provider_id: str,
    filters: ConnectionListFilters,
) -> ColumnElement[bool]:
    """AND all active filters; always scopes to provider_id."""
    clauses: list[ColumnElement[bool]] = [
        ProviderConnection.provider == provider_id,
    ]
    data = _data_jsonb()

    q = (filters.q or "").strip()
    if q:
        pattern = f"%{q}%"
        display = data["displayName"].as_string()
        clauses.append(
            or_(
                ProviderConnection.name.ilike(pattern),
                ProviderConnection.email.ilike(pattern),
                display.ilike(pattern),
            )
        )

    if filters.is_active is not None:
        clauses.append(
            ProviderConnection.is_active.is_(filters.is_active)
        )

    if filters.auth_type:
        clauses.append(
            ProviderConnection.auth_type == filters.auth_type
        )

    if filters.test_status:
        status = filters.test_status.strip().lower()
        status_col = func.lower(data["testStatus"].as_string())
        if status in CONNECTED_TEST_STATUSES:
            clauses.append(
                status_col.in_(sorted(CONNECTED_TEST_STATUSES))
            )
        else:
            clauses.append(status_col == status)

    if filters.proxy_pool_id is not None:
        clauses.append(
            ProviderConnection.proxy_pool_id
            == filters.proxy_pool_id
        )
    elif filters.has_proxy is True:
        clauses.append(
            ProviderConnection.proxy_pool_id.is_not(None)
        )
    elif filters.has_proxy is False:
        clauses.append(
            ProviderConnection.proxy_pool_id.is_(None)
        )

    if filters.token_issue:
        expires_raw = data["expiresAt"].as_string()
        last_err = data["lastError"].as_string()
        now_iso = datetime.now(timezone.utc).isoformat()
        expired = and_(
            expires_raw.is_not(None),
            expires_raw != "",
            expires_raw < now_iso,
        )
        refresh_err = and_(
            last_err.is_not(None),
            last_err != "",
        )
        if filters.token_issue == "expired":
            clauses.append(expired)
        elif filters.token_issue == "refresh_error":
            clauses.append(refresh_err)
        else:
            clauses.append(or_(expired, refresh_err))

    if filters.in_cooldown is not None:
        # modelLock_* keys with future ISO timestamps in JSON object
        cooldown_exists = text(
            """
            EXISTS (
              SELECT 1
              FROM jsonb_each_text(
                CAST(provider_connections.data AS jsonb)
              ) AS kv(key, value)
              WHERE kv.key LIKE 'modelLock_%'
                AND kv.value <> ''
                AND kv.value > :now_iso
            )
            """
        ).bindparams(
            now_iso=datetime.now(timezone.utc).isoformat()
        )
        if filters.in_cooldown:
            clauses.append(cooldown_exists)
        else:
            clauses.append(~cooldown_exists)

    return and_(*clauses)
```

Notes for implementer:
- Prefer `.as_string()` / dialect-appropriate JSON accessors that compile on Postgres. If `.as_string()` is unavailable in this SQLAlchemy version, use `data['displayName'].astext` or `data['displayName'].as_string()` per installed version — adjust tests to match compiled SQL.
- Keep lines ≤ 80 chars.
- Do not import unused `false`/`true`/`literal`/`exists`/`String` if unused after final code.

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && PYTHONPATH=. ../.venv-test/bin/python -m pytest \
  tests/test_connection_filters.py -q
```

Expected: PASS (fix SQL accessor names if compile output differs).

- [ ] **Step 5: Commit** (when user/execution mode allows)

```bash
git add backend/app/routers/providers/connection_filters.py \
  backend/tests/test_connection_filters.py
git commit -m "feat(providers): add connection list filter predicates"
```

---

### Task 2: Wire filters into list endpoint + `total_all`

**Files:**
- Modify: `backend/app/routers/providers/connections.py` (`list_provider_connections`)
- Test: extend `backend/tests/test_connection_filters.py` with a pure helper test for parsing query params if extracted; otherwise manual curl verification in Step 4

**Interfaces:**
- Consumes: `ConnectionListFilters`, `build_connection_filter_clause`
- Produces: list response includes `total_all: int`; `total` uses filtered clause; `connectionIds` uses filtered clause; models union still uses `provider == id` only

- [ ] **Step 1: Add query params to `list_provider_connections`**

In `connections.py`, import filters and extend signature:

```python
from uuid import UUID

from app.routers.providers.connection_filters import (
    ConnectionListFilters,
    build_connection_filter_clause,
)

@router.get("/providers/by-provider/{provider_id}/connections")
async def list_provider_connections(
    provider_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    include_ids: bool = Query(False),
    include_models: bool = Query(True),
    q: str | None = Query(None),
    is_active: bool | None = Query(None),
    test_status: str | None = Query(None),
    auth_type: str | None = Query(None),
    has_proxy: bool | None = Query(None),
    proxy_pool_id: UUID | None = Query(None),
    token_issue: str | None = Query(
        None,
        pattern="^(expired|refresh_error|any)$",
    ),
    in_cooldown: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
```

- [ ] **Step 2: Build clauses and counts**

Replace the single `where = ProviderConnection.provider == provider_id` usage for list/count/ids with:

```python
    filters = ConnectionListFilters(
        q=q,
        is_active=is_active,
        test_status=test_status,
        auth_type=auth_type,
        has_proxy=has_proxy,
        proxy_pool_id=proxy_pool_id,
        token_issue=token_issue,  # type: ignore[arg-type]
        in_cooldown=in_cooldown,
    )
    provider_only = ProviderConnection.provider == provider_id
    where = build_connection_filter_clause(provider_id, filters)

    # Heal priorities still uses provider_id only (page == 1)
    if page == 1 and await _priorities_need_renumber(db, provider_id):
        await _renumber_provider_priorities(db, provider_id)
        await db.flush()

    total_all = int(
        await db.scalar(
            select(func.count())
            .select_from(ProviderConnection)
            .where(provider_only)
        )
        or 0
    )
    total_i = int(
        await db.scalar(
            select(func.count())
            .select_from(ProviderConnection)
            .where(where)
        )
        or 0
    )

    offset = (page - 1) * page_size
    page_result = await db.execute(
        select(ProviderConnection)
        .where(where)
        .order_by(
            ProviderConnection.priority,
            ProviderConnection.id,
        )
        .offset(offset)
        .limit(page_size)
    )
```

Keep `include_models` blob query on `provider_only` (all connections).

`include_ids` query must use `where` (filtered).

Payload:

```python
    payload: dict = {
        "provider": provider_id,
        "total": total_i,
        "total_all": total_all,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
```

- [ ] **Step 3: Syntax / import check**

```bash
cd backend && PYTHONPATH=. ../.venv-test/bin/python -c \
  "from app.routers.providers.connections import list_provider_connections"
```

Expected: no ImportError.

- [ ] **Step 4: Manual API smoke (running backend on host port)**

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8013/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"password":"123456"}' | ../.venv-test/bin/python -c \
  'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Pick a provider id that has many connections, e.g. from overview
curl -s "http://127.0.0.1:8013/providers/by-provider/PROVIDER/connections?page=1&page_size=10&is_active=false" \
  -H "Authorization: Bearer $TOKEN" | ../.venv-test/bin/python -c \
  'import sys,json; d=json.load(sys.stdin); print(d["total"], d["total_all"], len(d["items"]))'
```

Expected: `total <= total_all`; items length ≤ 10; inactive-only when filtered.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/providers/connections.py
git commit -m "feat(providers): filter paginated connections + total_all"
```

---

### Task 3: Frontend filter state + fetch wiring

**Files:**
- Modify: `frontend/src/pages/ProviderDetailPage.jsx`

**Interfaces:**
- Consumes: API `total`, `total_all`, filter query params from Task 2
- Produces: UI state `connectionFilters` + debounced `q`; `fetchConnections` sends params; `connectionTotalAll` state

- [ ] **Step 1: Add filter state next to pagination state**

Near `connectionPage` / `connectionTotal`:

```javascript
  const [connectionTotalAll, setConnectionTotalAll] = useState(0)
  const [connSearchInput, setConnSearchInput] = useState('')
  const [connSearchQ, setConnSearchQ] = useState('')
  const [connFilterActive, setConnFilterActive] = useState('') // '' | 'true' | 'false'
  const [connFilterStatus, setConnFilterStatus] = useState('')
  const [connFilterAuth, setConnFilterAuth] = useState('')
  const [connFilterProxy, setConnFilterProxy] = useState('') // '' | 'yes' | 'no'
  const [connFilterPoolId, setConnFilterPoolId] = useState('')
  const [connFilterToken, setConnFilterToken] = useState('')
  const [connFilterCooldown, setConnFilterCooldown] = useState('') // '' | 'yes' | 'no'
```

Add refs for filters used inside `fetchConnections` (same pattern as `connectionPageRef`) **or** include filter values in the `useCallback` dependency list and the inflight load key.

Debounce search:

```javascript
  useEffect(() => {
    const t = setTimeout(() => {
      setConnSearchQ(connSearchInput.trim())
    }, 300)
    return () => clearTimeout(t)
  }, [connSearchInput])
```

- [ ] **Step 2: Build params inside `fetchConnections`**

```javascript
      const params = {
        page,
        page_size: CONNECTIONS_PER_PAGE,
        include_models: true,
      }
      if (connSearchQ) params.q = connSearchQ
      if (connFilterActive === 'true') params.is_active = true
      if (connFilterActive === 'false') params.is_active = false
      if (connFilterStatus) params.test_status = connFilterStatus
      if (connFilterAuth) params.auth_type = connFilterAuth
      if (connFilterProxy === 'yes') params.has_proxy = true
      if (connFilterProxy === 'no') params.has_proxy = false
      if (connFilterPoolId) params.proxy_pool_id = connFilterPoolId
      if (connFilterToken) params.token_issue = connFilterToken
      if (connFilterCooldown === 'yes') params.in_cooldown = true
      if (connFilterCooldown === 'no') params.in_cooldown = false

      const [connRes, proxyRes] = await Promise.all([
        providersApi.getProviderConnections(pid, params),
        proxyPoolsApi.getAll(),
      ])
      // ...
      setConnectionTotal(payload.total || 0)
      setConnectionTotalAll(
        payload.total_all != null
          ? payload.total_all
          : (payload.total || 0),
      )
```

Update the StrictMode inflight key to include a stable filter signature (e.g. `JSON.stringify(params without page)` + page) so filter changes refetch.

- [ ] **Step 3: Reset page when filters change**

```javascript
  useEffect(() => {
    setConnectionPage(1)
  }, [
    connSearchQ,
    connFilterActive,
    connFilterStatus,
    connFilterAuth,
    connFilterProxy,
    connFilterPoolId,
    connFilterToken,
    connFilterCooldown,
  ])
```

Ensure the existing page/`fetchConnections` effect still runs after reset (page 1 + new filters).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProviderDetailPage.jsx
git commit -m "feat(providers): wire connection filter params into list fetch"
```

---

### Task 4: Filter bar UI, footer, empty states, select-all label

**Files:**
- Modify: `frontend/src/pages/ProviderDetailPage.jsx` (connection list section ~2528–2660)

**Interfaces:**
- Consumes: filter state from Task 3; `connectionTotal`, `connectionTotalAll`

- [ ] **Step 1: Helper for “filters active”**

```javascript
  const connFiltersActive = Boolean(
    connSearchQ ||
    connFilterActive ||
    connFilterStatus ||
    connFilterAuth ||
    connFilterProxy ||
    connFilterPoolId ||
    connFilterToken ||
    connFilterCooldown
  )

  const clearConnFilters = () => {
    setConnSearchInput('')
    setConnSearchQ('')
    setConnFilterActive('')
    setConnFilterStatus('')
    setConnFilterAuth('')
    setConnFilterProxy('')
    setConnFilterPoolId('')
    setConnFilterToken('')
    setConnFilterCooldown('')
  }
```

- [ ] **Step 2: Header count uses `total_all`**

Change the header line that prints connection count to use `connectionTotalAll` (fallback `connectionTotal`).

- [ ] **Step 3: Insert filter bar above “This page”**

Before the select-all row, add a wrapping flex bar with:
- text input bound to `connSearchInput`
- `<select>` for Active / Status / Auth / Proxy / Token / Cooldown
- optional pool `<select>` when `activePools.length > 0`
- Clear button when `connFiltersActive`

Hide Auth select when provider is clearly single-auth (`isOAuth` only or API-only) if that boolean already exists; otherwise always show.

Hide Token select when `!isOAuth`.

Status options: empty, `connected`, `error`, `expired`, `unavailable`, `untested`, `unknown`.

- [ ] **Step 4: Empty filtered state**

When `connectionTotalAll > 0 && connectionTotal === 0 && connFiltersActive`, show “No connections match filters” + Clear — do **not** show “No connections yet”.

When `connectionTotalAll === 0`, keep existing empty create/import UI.

- [ ] **Step 5: Footer + Select All label**

```javascript
  // Footer
  {connStart + 1}–{connEnd} of {connectionTotal}
  {connFiltersActive && connectionTotalAll > connectionTotal
    ? ` · filtered from ${connectionTotalAll}`
    : ''}

  // Button
  Select All{connFiltersActive ? ' filtered' : ''} ({connectionTotal})
```

Show pagination when `connectionTotal > CONNECTIONS_PER_PAGE` (filtered total).

- [ ] **Step 6: Manual UI check**

Open `/providers/<id>` with many connections:
1. Filter Inactive → only inactive; footer shows filtered from N
2. Search email → hit not on page 1
3. Select All filtered → selection count equals filtered total after fetch ids path
4. Clear filters → full list

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ProviderDetailPage.jsx
git commit -m "feat(providers): connection filter bar, footer, empty states"
```

---

### Task 5: Select-all-pages uses filtered ids

**Files:**
- Modify: `frontend/src/pages/ProviderDetailPage.jsx` (`handleSelectAllPages` / any `include_ids: true` call)

**Interfaces:**
- Consumes: same filter params as `fetchConnections`

- [ ] **Step 1: Find `include_ids` usage**

Search in `ProviderDetailPage.jsx` for `include_ids` / `connectionIds` / `handleSelectAllPages`.

- [ ] **Step 2: Pass the same filter params** when requesting ids so bulk select only returns filtered ids.

- [ ] **Step 3: Manual check** — filter error, Select All filtered, confirm count matches `total`, not `total_all`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProviderDetailPage.jsx
git commit -m "fix(providers): select-all respects connection filters"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Server-side AND filters | 1–2 |
| Search name/email/displayName | 1 |
| `total` + `total_all` | 2–4 |
| Filter bar UI | 4 |
| Debounced search | 3 |
| Reset page on filter change | 3 |
| Footer filtered copy | 4 |
| Empty filtered vs empty provider | 4 |
| Select-all filtered | 4–5 |
| Models union unfiltered | 2 |
| No client-only page filter | — |

## Placeholder / consistency review

- No TBD steps.
- Param names match between Tasks 1–4 (`q`, `is_active`, `test_status`, `auth_type`, `has_proxy`, `proxy_pool_id`, `token_issue`, `in_cooldown`).
- Response fields `total` / `total_all` consistent.
- JSON accessor API may need a one-line adjust for the installed SQLAlchemy version — covered in Task 1 notes.
