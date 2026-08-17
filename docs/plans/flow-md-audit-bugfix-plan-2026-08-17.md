# Plan: Provider Bugfixes from FLOW.md Audit — 2026-08-17

**Status:** completed (2026-08-17)

Implemented and independently re-verified. No further code
changes required for this plan. Commit is still the user's
call (not done by the implementing agent).

Verification (`cd backend && PYTHONPATH=. .venv/bin/pytest`):
- `tests/test_mistral_transform.py -k alims` — 3 passed
- `tests/test_quota_handlers.py -k nvidia` — 13 passed
- `Known bug` gone from alims-intl and nvidia FLOW.md
- `observe_response` unchanged; 90 s TTL covers the whole
  overlay (match-merge and leftover append)

Live DashScope 200 / NVIDIA 429 were not exercised.

> Historical note: this file was the executing-agent brief
> (Bahasa Indonesia to the user; English code/docs; no
> commit unless asked). Do not re-run the tasks.

**Revision:** 2 (2026-08-17). Rewritten after an independent
validation of v1. v1 Task 1 (alims URL) is unchanged in design.
v1 Task 2 (nvidia) was unsafe: it applied the 90 s stale guard
only to appended leftover rows, so a renamed RPM merge would
pin a rare 429 snapshot on the RPM bar forever. v1 also pointed
at the wrong tests (grok-cli around line 493) and a missing
pytest binary (`.venv-local`). This revision fixes those.

**Goal:** Fix the two code bugs surfaced by
`.scratch/flow-md-audit-2026-08-17.md`. Remove the `Known bug`
notes from the two FLOW.md files after the code matches.

**Architecture:** Both bugs are isolated inside one provider
folder each (PS Rule). Alims: normalize the rerank URL so
`/compatible-mode/v1` appears once. Nvidia: make observe/fetch
quota row names match, then overlay a *fresh* header cache onto
local counts. Extract a sync helper in each file so tests do
not need a live DB or network.

**Tech stack:** FastAPI backend, pytest, existing
`test_mistral_transform.py` + `test_quota_handlers.py`.

---

## Global constraints

- Touch only:
  - `backend/app/providers/alims_intl/handler.py`
  - `backend/app/providers/alims_intl/FLOW.md`
  - `backend/app/providers/nvidia/quota.py`
  - `backend/app/providers/nvidia/FLOW.md`
  - `backend/tests/test_mistral_transform.py`
  - `backend/tests/test_quota_handlers.py`
- No new DB columns, no router/frontend changes, no container
  rebuild (volume mounts pick up edits).
- No auto-commit. Stop and report after each task.
- Preserve working paths:
  - alims rerank must keep working for connections that already
    set a host-root custom `baseUrl`
  - nvidia tracker must keep showing local counts when NVIDIA
    never sends headers (the common case)
- Pytest (from `backend/`, host `backend/.venv` — the same
  venv as local `uv run uvicorn`):

  ```bash
  cd backend
  PYTHONPATH=. .venv/bin/pytest <args> -v
  ```

  Do not recreate repo-root extras (`.venv-test`,
  `.venv-local`). Prod image venv is separate.

---

## Why the previous plan was patched

| v1 claim | Reality |
|----------|---------|
| Guard 90 s only on appended leftover rows | After rename, the RPM header row **matches** the local RPM bar. Merge has no TTL → one 429 (`observe` replaces the whole cache; success responses omit headers) pins `used` forever. **Worse than today's dead overlay.** |
| "tests around lines 493–535" | Those are **grok-cli** `handler.fetch("", {})` tests. They read `provider_data`, no DB. Nvidia `fetch` always calls `_count_requests` (SQL) then `QuotaCache`. |
| `../.venv-local/bin/pytest` | Missing. Host venv is `backend/.venv`. |
| Nvidia tests start ~751 | `test_nvidia_handler_registered` at line 751. |

---

## Current ground truth (do not re-audit; implement)

### Alims rerank

`AlimsIntlConfig.BASE_URL` =

```
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

`BaseProviderHandler._resolve_base_url` (`providers/base.py:211`)
returns `data.baseUrl` (rstrip `/`) or that `BASE_URL`.

`AlimsIntlHandler.execute_rerank` line 91:

```python
url = f"{base_url.rstrip('/')}/compatible-mode/v1/reranks"
```

Default request (no custom `baseUrl`):

```
https://dashscope-intl.aliyuncs.com/compatible-mode/v1/compatible-mode/v1/reranks
```

`alims_intl/bulk.py` documents optional farm field `host` and
discards it. Bulk-imported connections therefore also hit the
default (doubled) URL. **Do not change `bulk.py`.** After URL
normalization the default host works.

### Nvidia overlay

`quotas_from_headers` writes `"NIM requests (RPM)"` (and
`"NIM requests (header)"` when header limit ≠ config rpm).

`apply_local_usage` writes `"NIM requests (today)"` and
`"NIM requests (last 60s / RPM)"`.

`NvidiaUsageHandler.fetch` (lines 336–353) merges only when
`q["name"] == row["name"]`. Names never match → overlay is
dead. Tracker is still honest (local counts only).

`observe_response` still replaces the whole cache with header
rows and sets `fetched_at`. Do not change that behavior.

NVIDIA omits rate-limit headers on most success responses.
A 429 snapshot in `quota_cache` will not be refreshed.

### Docs already updated

`alims_intl/FLOW.md` and `nvidia/FLOW.md` describe the bugs
and point at this plan. After each task, replace the `Known
bug` paragraph with the post-fix behavior (exact text below).
`openrouter/FLOW.md` and `mistral/FLOW.md` were already
corrected; do not edit them.

---

## Files

| File | Role in this plan |
|------|-------------------|
| `alims_intl/handler.py` | Add `rerank_url`; call it from `execute_rerank` |
| `alims_intl/FLOW.md` | Replace `Known bug` with normalized URL rule |
| `nvidia/quota.py` | Rename RPM bar; add `_HEADER_STALE_SEC` + `overlay_header_cache`; call it from `fetch` |
| `nvidia/FLOW.md` | Replace `Known bug` with overlay + 90 s rule |
| `tests/test_mistral_transform.py` | Append `rerank_url` cases after existing alims test (line 356) |
| `tests/test_quota_handlers.py` | Tighten nvidia name assert; add overlay helper tests + one fetch wiring test after line 790 |

---

## Task 1: alims-intl rerank URL normalization

**Files:**
- Modify: `backend/app/providers/alims_intl/handler.py`
- Modify: `backend/app/providers/alims_intl/FLOW.md` (lines 68–73)
- Test: `backend/tests/test_mistral_transform.py` (append after
  `test_alims_drops_invalid_reasoning_effort`)

**Do not:** edit `bulk.py`, invent a Beijing `compatible-api`
branch, hit the network, or change `prepare_request`.

### Result matrix (must hold after the helper exists)

| Resolved `baseUrl` | Endpoint |
|---|---|
| default `AlimsIntlConfig.BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1/reranks` |
| same + trailing `/` | same (one segment) |
| workspace SG `https://ws.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` | `https://ws.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/reranks` |
| host-root `https://host.example` | `https://host.example/compatible-mode/v1/reranks` |
| `""` / `None` coerced to `""` | `/compatible-mode/v1/reranks` |

Count of the substring `/compatible-mode/v1` in every non-empty
result must be exactly `1`.

- [x] **Step 1: Write the failing tests**

Append to `backend/tests/test_mistral_transform.py`. Keep
imports inside the test (same style as the existing alims
test at line 356) so the mistral-only header stays clean.

```python
def test_alims_rerank_url_default_not_doubled() -> None:
    from app.providers.alims_intl.config import AlimsIntlConfig
    from app.providers.alims_intl.handler import rerank_url

    url = rerank_url(AlimsIntlConfig.BASE_URL)
    assert url.count("/compatible-mode/v1") == 1
    assert url.endswith("/compatible-mode/v1/reranks")
    assert url == (
        "https://dashscope-intl.aliyuncs.com"
        "/compatible-mode/v1/reranks"
    )


def test_alims_rerank_url_shapes() -> None:
    from app.providers.alims_intl.handler import rerank_url

    assert rerank_url(
        "https://ws.ap-southeast-1.maas.aliyuncs.com"
        "/compatible-mode/v1"
    ) == (
        "https://ws.ap-southeast-1.maas.aliyuncs.com"
        "/compatible-mode/v1/reranks"
    )
    assert rerank_url("https://host.example") == (
        "https://host.example/compatible-mode/v1/reranks"
    )
    assert rerank_url(
        "https://dashscope-intl.aliyuncs.com"
        "/compatible-mode/v1/"
    ).count("/compatible-mode/v1") == 1
    assert rerank_url("") == "/compatible-mode/v1/reranks"
```

- [x] **Step 2: Run tests — expect FAIL**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest \
  tests/test_mistral_transform.py -k alims_rerank -v
```

Expected: `ImportError` (`rerank_url` missing) or assert fail.

- [x] **Step 3: Implement the helper and wire it**

In `backend/app/providers/alims_intl/handler.py`, add this
**above** `class AlimsIntlHandler` (module-level, so tests
import it without constructing a handler):

```python
_COMPAT_SUFFIX = "/compatible-mode/v1"


def rerank_url(base_url: str) -> str:
    """Compatible-mode rerank endpoint for any base URL shape."""
    root = (base_url or "").rstrip("/")
    if root.endswith(_COMPAT_SUFFIX):
        root = root[: -len(_COMPAT_SUFFIX)]
    return f"{root}{_COMPAT_SUFFIX}/reranks"
```

In `execute_rerank`, replace **only** line 91:

```python
# before
url = f"{base_url.rstrip('/')}/compatible-mode/v1/reranks"

# after
url = rerank_url(base_url)
```

Do not change the request body, headers, or response mapping.

- [x] **Step 4: Re-run alims tests — expect PASS**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest \
  tests/test_mistral_transform.py -k alims -v
```

Expected: `test_alims_drops_invalid_reasoning_effort` still
passes, plus the two new tests.

- [x] **Step 5: Update FLOW.md**

Replace the bullet at `alims_intl/FLOW.md` lines 68–73
(the `Known bug` + plan pointer) with:

```markdown
- Rerank: `execute_rerank` POSTs
  `{root}/compatible-mode/v1/reranks` where `root` is the
  resolved baseUrl with a trailing `/compatible-mode/v1`
  stripped (`rerank_url`). Default `BASE_URL`, workspace
  SG/EU hosts that already end in that suffix, and a
  host-root custom `baseUrl` all produce exactly one
  compatible-mode segment.
```

Confirm the file no longer contains `Known bug` or a pointer
to this plan.

- [x] **Step 6: Stop and report**

Report: helper + `execute_rerank` call + 2 tests + FLOW.md.
Do not start Task 2 in the same breath if anything failed.
Do not commit.

---

## Task 2: nvidia quota header overlay (with TTL)

**Files:**
- Modify: `backend/app/providers/nvidia/quota.py`
- Modify: `backend/app/providers/nvidia/FLOW.md` (lines 89–96)
- Test: `backend/tests/test_quota_handlers.py` (nvidia block
  starts at line 751; append after `test_nvidia_local_usage`
  at line 783)

**Do not:** change `observe_response` (it still replaces the
whole cache). Do not change `_count_requests`. Do not add a
DB migration. Do not copy grok-cli `handler.fetch("", {})`
tests — those do not hit nvidia's SQL path.

### Required behavior

1. `quotas_from_headers` RPM row name becomes
   `"NIM requests (last 60s / RPM)"` — **identical** to the
   `apply_local_usage` RPM bar (the merge key).
2. Extract `overlay_header_cache(rows, raw, fetched_at, now)`
   as a **sync** module-level helper. `fetch` loads cache then
   calls it. Tests cover the helper; they do not need Postgres.
3. **The 90 s guard wraps the entire overlay** (match-merge
   *and* leftover append). Copy mistral's age math
   (`mistral/quota.py:384-396`): missing `fetched_at` → treat
   as stale (`age = 10_000.0`). Naive datetimes → assume UTC.
4. Fresh cache:
   - matching names → `used = max(local, cached)`; keep local
     `total`; `reset_at = cached.reset_at or local.reset_at`
   - leftover cached rows whose name starts with
     `"NIM requests"` (i.e. `"NIM requests (header)"`) →
     append
5. Stale cache (`age > 90`) or missing `fetched_at` → return
   local rows unchanged.
6. Alias legacy name `"NIM requests (RPM)"` →
   `"NIM requests (last 60s / RPM)"` inside the helper so a
   cache written before this deploy still merge-matches for
   up to 90 s (no DB migration).

### Why the TTL must cover match-merge

`observe_response` replaces `quota_cache.quotas` with header
rows only. NVIDIA usually omits headers on success, so that
snapshot is not refreshed. If `fetch` takes
`max(local, cached)` on the renamed RPM bar with no age
check, one 429 with `remaining=0` freezes the bar at 40
until a later observe that may never come. Today's dead
overlay at least shows honest local counts. A rename-only
fix is a regression. **Reject any implementation that
merges matching names without the 90 s gate.**

- [x] **Step 1: Write the failing tests**

In `backend/tests/test_quota_handlers.py`:

1. Add to the nvidia import block (lines 35–40):

```python
from app.providers.nvidia.quota import (
    NvidiaUsageHandler,
    apply_local_usage as nv_apply_local_usage,
    lookup_limits as nv_lookup_limits,
    overlay_header_cache as nv_overlay_header_cache,
    quotas_from_headers as nv_quotas_from_headers,
)
```

2. Add near the other stdlib imports at the top of the file:

```python
import json
from datetime import datetime, timedelta, timezone
```

   (`json` may already be unused-absent; add only what the
   file does not already import. Do not reorder the existing
   provider import block beyond the nvidia lines.)

3. Tighten `test_nvidia_quotas_from_headers` so the name is
   exact (the `"RPM" in name` check still passes after
   rename, so without this the old test stays green and
   hides a missed rename):

```python
def test_nvidia_quotas_from_headers() -> None:
    headers = {
        "X-RateLimit-Limit": "40",
        "X-RateLimit-Remaining": "12",
    }
    rows = nv_quotas_from_headers(headers, "free")
    rpm = next(
        r for r in rows
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["total"] == 40
    assert rpm["remaining"] == 12
    assert rpm["used"] == 28
```

4. Append these tests after `test_nvidia_local_usage`:

```python
def test_nvidia_header_row_name_matches_local() -> None:
    hdr = nv_quotas_from_headers(
        {
            "X-RateLimit-Limit": "40",
            "X-RateLimit-Remaining": "12",
        },
        "free",
    )
    local = nv_apply_local_usage("free", 1, 0)
    hdr_names = {r["name"] for r in hdr}
    local_names = {r["name"] for r in local}
    assert "NIM requests (last 60s / RPM)" in hdr_names
    assert "NIM requests (last 60s / RPM)" in local_names


def test_nvidia_overlay_max_used_when_fresh() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 10,
        "total": 40,
        "remaining": 30,
        "reset_at": "cached-reset",
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 10
    assert rpm["total"] == 40
    assert rpm["reset_at"] == "cached-reset"


def test_nvidia_overlay_keeps_higher_local() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 12, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 3,
        "total": 40,
        "remaining": 37,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 12


def test_nvidia_overlay_ignores_stale_cache() -> None:
    now = datetime.now(timezone.utc)
    stale = now - timedelta(seconds=91)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 40,
        "total": 40,
        "remaining": 0,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, stale, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 2
    assert all(
        r["name"] != "NIM requests (header)" for r in out
    )


def test_nvidia_overlay_missing_fetched_at_is_stale() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 40,
        "total": 40,
        "remaining": 0,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, None, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 2


def test_nvidia_overlay_appends_fresh_header_row() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (header)",
        "used": 5,
        "total": 80,
        "remaining": 75,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    extra = next(
        r for r in out
        if r["name"] == "NIM requests (header)"
    )
    assert extra["used"] == 5
    assert extra["total"] == 80


def test_nvidia_overlay_aliases_legacy_rpm_name() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (RPM)",
        "used": 9,
        "total": 40,
        "remaining": 31,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 9
    assert all(
        r["name"] != "NIM requests (RPM)" for r in out
    )
```

5. One fetch wiring test so `fetch` actually calls the helper
   (do **not** copy grok-cli tests). Patch `_count_requests`
   and `app.database.async_session`. Use a real UUID string
   because `fetch` does `uuid.UUID(connection_id)`.

```python
@pytest.mark.asyncio
async def test_nvidia_fetch_applies_fresh_overlay() -> None:
    cid = "11111111-1111-1111-1111-111111111111"
    now = datetime.now(timezone.utc)
    cache = MagicMock()
    cache.quotas = json.dumps([{
        "name": "NIM requests (last 60s / RPM)",
        "used": 10,
        "total": 40,
        "remaining": 30,
        "reset_at": None,
        "unlimited": False,
    }])
    cache.fetched_at = now
    db = AsyncMock()
    db.get = AsyncMock(return_value=cache)
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = db
    session_cm.__aexit__.return_value = False

    handler = NvidiaUsageHandler()
    with (
        patch(
            "app.providers.nvidia.quota._count_requests",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch(
            "app.database.async_session",
            return_value=session_cm,
        ),
    ):
        result = await handler.fetch(
            "", {"accountType": "free"}, cid,
        )
    rpm = next(
        q for q in result.quotas
        if q.name == "NIM requests (last 60s / RPM)"
    )
    assert rpm.used == 10
```

- [x] **Step 2: Run nvidia tests — expect FAIL**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest \
  tests/test_quota_handlers.py -k nvidia -v
```

Expected: `ImportError` for `overlay_header_cache` and/or
`test_nvidia_quotas_from_headers` fail on the exact name
`"NIM requests (last 60s / RPM)"`. Existing
`test_nvidia_local_usage` / `test_nvidia_config_limits` /
`test_nvidia_handler_registered` must still be collected.

- [x] **Step 3: Implement**

In `backend/app/providers/nvidia/quota.py`, next to the
other module constants (`_LIMIT`, …), add:

```python
_HEADER_STALE_SEC = 90
_RPM_BAR = "NIM requests (last 60s / RPM)"
_LEGACY_RPM_BAR = "NIM requests (RPM)"
```

In `quotas_from_headers`, change **only** the RPM name
string (line 148) from `"NIM requests (RPM)"` to `_RPM_BAR`.
Leave the `"NIM requests (header)"` branch as-is.

Add these helpers **above** `class NvidiaUsageHandler`
(near `apply_local_usage`):

```python
def _cache_age_sec(
    fetched_at: datetime | None,
    now: datetime,
) -> float:
    """Seconds since cache write; missing stamp counts as stale."""
    if fetched_at is None:
        return 10_000.0
    fetched = fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return (now - fetched).total_seconds()


def overlay_header_cache(
    rows: list[dict],
    raw: object,
    fetched_at: datetime | None,
    now: datetime,
) -> list[dict]:
    """Overlay a fresh header cache onto local quota bars.

    Stale cache (age > 90 s, or no fetched_at) is ignored.
    NVIDIA rarely sends headers on success, so a 429
    snapshot must not pin the RPM bar.
    """
    if not isinstance(raw, list):
        return rows
    if _cache_age_sec(fetched_at, now) > _HEADER_STALE_SEC:
        return rows

    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name == _LEGACY_RPM_BAR:
            name = _RPM_BAR
        if not name:
            continue
        matched = False
        for row in rows:
            if row["name"] != name:
                continue
            matched = True
            used = int(item.get("used") or 0)
            if used > int(row["used"] or 0):
                row.update(_item(
                    row["name"],
                    used=used,
                    total=row["total"],
                    reset_at=(
                        item.get("reset_at")
                        or row["reset_at"]
                    ),
                ))
            break
        if matched:
            continue
        if name.startswith("NIM requests"):
            extra = dict(item)
            extra["name"] = name
            rows.append(extra)
    return rows
```

In `NvidiaUsageHandler.fetch`, replace the inner
`if isinstance(raw, list):` loop (lines 335–353) with:

```python
                if isinstance(raw, list):
                    rows = overlay_header_cache(
                        rows,
                        raw,
                        cache.fetched_at,
                        now,
                    )
```

Keep the `json.loads` / except block. Keep
`observe_response` untouched.

- [x] **Step 4: Re-run nvidia tests — expect PASS**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest \
  tests/test_quota_handlers.py -k nvidia -v
```

Expected: all previous nvidia tests + new overlay / fetch
tests green. In particular
`test_nvidia_overlay_ignores_stale_cache` must pass — that
is the regression the v1 plan would have shipped.

- [x] **Step 5: Update FLOW.md**

Replace `nvidia/FLOW.md` lines 89–96 (`observe` cache names
+ `Known bug` + plan pointer) with:

```markdown
`observe_response` no-ops when those headers are missing. It
caches rows named `NIM requests (last 60s / RPM)` (same
merge key as the local RPM bar) and, when the header limit
differs from config rpm, `NIM requests (header)`.

`fetch` overlays a fresh cache (`fetched_at` ≤ 90 s) onto
local counts: matching names take `max(local used, cached
used)`; leftover `NIM requests*` rows are appended. A stale
or timestamp-less cache is ignored so a rare 429 snapshot
cannot pin the RPM bar. No headers (the common case) →
local counts only.
```

Confirm the file no longer contains `Known bug` or a pointer
to this plan.

- [x] **Step 6: Stop and report**

Report: rename + helper + `fetch` call + tests + FLOW.md.
List the exact pytest command and the pass count. Do not
commit.

---

## Task 3: final sweep

- [x] **Step 1: Combined pytest**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest \
  tests/test_quota_handlers.py \
  tests/test_mistral_transform.py -v
```

Expected: full green, including non-nvidia / non-alims
cases in those two files (mistral transform, groq, openrouter,
cerebras, cohere, grok-cli). If an unrelated test is already
red before your edits, say so — do not "fix" it.

- [x] **Step 2: Lint the two provider folders**

```bash
cd backend
.venv/bin/ruff check \
  app/providers/alims_intl \
  app/providers/nvidia
```

If `ruff` is missing from `.venv`, try
`.venv/bin/python -m ruff check …`. Do not install
packages. If ruff is unavailable, skip and say so.

- [x] **Step 3: Doc + scope check**

- `rg "Known bug" backend/app/providers/alims_intl/FLOW.md backend/app/providers/nvidia/FLOW.md`
  → no matches
- `git diff --stat` shows only the six files listed under
  Global constraints
- `rerank_url` and `overlay_header_cache` have parameter and
  return annotations
- no new files under `/tmp` or untracked scratch dirs

- [x] **Step 4: Stop — ask the user before commit**

Report in Bahasa Indonesia:

- what changed in each of the six files
- pytest command + result
- ruff result
- anything you did not verify (e.g. live DashScope 200, live
  NVIDIA 429)

Do not `git add` / `commit` / `push`.

---

## Out of scope (do not touch)

- `openrouter/` — HIGH audit finding was doc-only; FLOW.md
  already says chat proxy sends Bearer only.
- `mistral/` FLOW.md — the 7 LOW nuances are already written.
- `groq/` / `cerebras/` / `cohere/` optional LOW notes
  (inherited `FORMAT`, compound TPD, `overlay_live_on_published`
  wording, hardcoded `"free"` observe cap, rerank default
  model `rerank-english-v2.0`).
- `alims_intl/bulk.py` still discards farm `host` / `password`
  / `proxy`. After Task 1 the default DashScope host works;
  persisting workspace `host` is a separate feature.
- Beijing workspace `compatible-api/v1` (handler docstring).
  Pre-existing; this plan only de-duplicates
  `/compatible-mode/v1`.
- Free-form cache `plan` strings (`"International"`,
  `"Groq org"`, `"mistral"`).
- Cross-provider `parse_expires_at` import (PS Rule spirit,
  not a bug).
- Adding `SERVICE_KINDS` to FLOW.md constants blocks.

---

## Spec coverage

| Requirement | Task |
|-------------|------|
| Default alims rerank URL not doubled | 1 |
| Workspace SG / host-root still one segment | 1 |
| Trailing slash tolerated | 1 |
| `execute_rerank` uses the helper | 1 |
| alims FLOW.md post-fix (no `Known bug`) | 1 |
| Header RPM name == local RPM name | 2 |
| `max(local, cached)` when cache ≤ 90 s | 2 |
| Stale / missing `fetched_at` ignored | 2 |
| Leftover `NIM requests (header)` appended if fresh | 2 |
| Legacy `"NIM requests (RPM)"` aliases onto new bar | 2 |
| `observe_response` still replace-all | 2 |
| No-header path still local-only | 2 (unchanged observe + stale skip) |
| nvidia FLOW.md post-fix (no `Known bug`) | 2 |
| Combined tests + ruff + six-file diff | 3 |
| No commit | 3 |

## Placeholder / consistency self-review

- No TBD steps. Helper names locked: `rerank_url`,
  `overlay_header_cache`, `_HEADER_STALE_SEC = 90`,
  `_RPM_BAR`, `_LEGACY_RPM_BAR`.
- Pytest binary locked: `backend/.venv/bin/pytest`
  (`cd backend` + `PYTHONPATH=. .venv/bin/pytest`).
- Nvidia tests live after line 783, not 493.
- TTL applies to match-merge, not only leftover append.
