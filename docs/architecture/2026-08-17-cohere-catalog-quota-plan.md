# Cohere Catalog + Quota Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Cohere to SQL catalog (`MODEL_CATALOG_TABLE`), add an
Alibaba-Studio-style quota tracker (small summary + on-demand
per-model detail), and ship `FLOW.md`.

**Architecture:** Catalog flag on `CohereConfig` routes fetch/clear
through `provider_models`. `cohere/quota.py` auto-registers via
`services/quota` discovery (`USES_UPSTREAM = False`). List/refresh
persists only summary bars; `fetch_model_details` serves
`GET /usage/{id}?detail=models`. Plan caps use
`data.accountType` (`free` / `payg` / `subscribe`).

**Tech Stack:** FastAPI, SQLAlchemy async, pytest, React
(QuotaTrackerPage gate only).

**Spec:**
`docs/architecture/2026-08-17-cohere-catalog-quota-design.md`

## Global Constraints

- Code/docs English; chat with user Indonesian.
- No new columns on `provider_connections`.
- PS rule: Cohere logic only under `backend/app/providers/cohere/`.
- Do not dual-write catalog into `data.models` on fetch/clear.
- Max 80 characters per Python/JS line.
- Do **not** commit unless the user explicitly asks.
- Tests: `cd backend && ../.venv-local/bin/pytest …` if that venv
  exists, else `uv run pytest …` or `./.venv/bin/python -m pytest …`.
- Mirror Alibaba Studio summary + detail pattern; do not seed the
  full per-model table into `quota_cache`.

## File map

| File | Role |
|------|------|
| `backend/app/providers/cohere/config.py` | Catalog flag, `RATE_LIMITS`, notice |
| `backend/app/providers/cohere/quota.py` | **Create** summary + detail + observe |
| `backend/app/providers/cohere/FLOW.md` | **Create** from this folder’s code |
| `backend/tests/test_quota_handlers.py` | Register + unit tests for Cohere |
| `frontend/src/pages/QuotaTrackerPage.jsx` | Model-details button for `cohere` |
| `docs/architecture/2026-08-15-openrouter-catalog-slice.md` | Add `cohere` to on-list |

No registry edit needed: `app.services.quota` discovers
`providers/*/quota.py` automatically.

---

### Task 1: Config — catalog flag + RATE_LIMITS

**Files:**
- Modify: `backend/app/providers/cohere/config.py`
- Modify: `docs/architecture/2026-08-15-openrouter-catalog-slice.md`
- Test: `backend/tests/test_quota_handlers.py` (add config asserts
  in Task 3; this task unlocks them)

**Interfaces:**
- Produces: `CohereConfig.MODEL_CATALOG_TABLE = True`
- Produces: `CohereConfig.RATE_LIMITS` with keys
  `"{plan}/{model_or_endpoint}"` and monthly under
  `"free/_monthly": {"calls": 1000}`
- Consumes: account types `free` | `payg` | `subscribe` only

- [ ] **Step 1: Update `config.py`**

Set catalog flag and published limits from
https://docs.cohere.com/docs/rate-limits

Canonical Chat model ids (compatibility API style):

```
command-a-plus, command-a-reasoning, command-a-translate,
command-a-vision, command-a, command-r-plus, command-r,
command-r7b, north-mini-code
```

Use Cerebras-style compound keys. Example shape (fill every
plan/model required by the spec):

```python
MODEL_CATALOG_TABLE: bool = True
# Docs: docs.cohere.com/docs/rate-limits
# free = trial/evaluation key; payg/subscribe = production.
RATE_LIMITS: dict[str, dict[str, int]] = {
    # Monthly global (free / trial only)
    "free/_monthly": {"calls": 1000},
    # Chat per model — free 20 RPM
    "free/command-a": {"rpm": 20},
    "free/command-r-plus": {"rpm": 20},
    "free/command-r": {"rpm": 20},
    "free/command-r7b": {"rpm": 20},
    "free/north-mini-code": {"rpm": 20},
    "free/command-a-plus": {"rpm": 20},
    "free/command-a-reasoning": {"rpm": 20},
    "free/command-a-translate": {"rpm": 20},
    "free/command-a-vision": {"rpm": 20},
    # Chat — payg / subscribe 500 RPM for standard models
    "payg/command-a": {"rpm": 500},
    "payg/command-r-plus": {"rpm": 500},
    "payg/command-r": {"rpm": 500},
    "payg/command-r7b": {"rpm": 500},
    "payg/north-mini-code": {"rpm": 500},
    # Newer variants stay 20 on paid (contact sales in docs)
    "payg/command-a-plus": {"rpm": 20},
    "payg/command-a-reasoning": {"rpm": 20},
    "payg/command-a-translate": {"rpm": 20},
    "payg/command-a-vision": {"rpm": 20},
    # Duplicate payg rows under subscribe/ (same caps)
    # Endpoints
    "free/rerank": {"rpm": 10},
    "payg/rerank": {"rpm": 1000},
    "subscribe/rerank": {"rpm": 1000},
    "free/embed": {"ipm": 2000},
    "payg/embed": {"ipm": 2000},
    "subscribe/embed": {"ipm": 2000},
}
```

Copy every `payg/...` Chat row to `subscribe/...` with identical
caps. Add `CATEGORY: str = "freeTier"` if other free-tier peers
set it (OpenRouter/NVIDIA); otherwise leave unset.

Update `CohereMetadata.notice` text to mention free = trial
(20 RPM Chat, 1000 calls/month) and payg/subscribe = production
Chat RPM for standard models.

- [ ] **Step 2: Update catalog slice doc**

In `docs/architecture/2026-08-15-openrouter-catalog-slice.md`,
change the “On as of …” line to include **cohere** after
`alims-intl`.

- [ ] **Step 3: Smoke-import**

```bash
cd backend && ../.venv-local/bin/python -c \
  "from app.providers.cohere.config import CohereConfig; \
   c=CohereConfig(); assert c.MODEL_CATALOG_TABLE; \
   assert c.RATE_LIMITS['free/_monthly']['calls']==1000; \
   assert c.RATE_LIMITS['payg/command-r']['rpm']==500; \
   print('ok', len(c.RATE_LIMITS))"
```

Expected: prints `ok` and a key count ≥ 30.

- [ ] **Step 4: Commit only if user asked**

Otherwise skip.

---

### Task 2: `quota.py` — summary + detail + observe

**Files:**
- Create: `backend/app/providers/cohere/quota.py`
- Test: covered in Task 3

**Interfaces:**
- Consumes: `CohereConfig.RATE_LIMITS`, connection
  `data.accountType`, `usage_history` for provider `cohere`
- Produces:
  - `lookup_limits(model_id, account_type) -> dict[str, int]`
  - `summary_quota_rows(minute_by_model, *, month_used, account_type, reset_at) -> list[dict]`
  - `apply_local_usage(account_type, minute_by_model, *, rpm_reset) -> list[dict]`
  - `quotas_from_headers(headers, model, account_type) -> list[dict]`
  - `class CohereUsageHandler(BaseUsageHandler)` with
    `PROVIDER_ID = "cohere"`, `USES_UPSTREAM = False`,
    `fetch`, `fetch_model_details`, `observe_response`

Follow `alims_intl/quota.py` structure (helpers + handler). Keep
the file focused; prefer ~400–550 lines over copying unused
Alibaba header variants.

- [ ] **Step 1: Create helper skeleton**

```python
"""Cohere usage handler — summary card + per-model detail.

Chat RPM is per model; rerank/embed are per endpoint; free plan
also has 1000 API calls / month (docs.cohere.com/docs/rate-limits).
List fetch stays tiny (Alibaba Studio pattern).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.cohere.config import CohereConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_LIMIT_REQ = "x-ratelimit-limit-requests"
_REMAIN_REQ = "x-ratelimit-remaining-requests"
_RESET_REQ = "x-ratelimit-reset-requests"


def _plan(account_type: str | None) -> str:
    plan = (account_type or "free").strip().lower()
    if plan not in ("free", "payg", "subscribe"):
        return "free"
    return plan


def _strip_prefix(model_id: str) -> str:
    raw = (model_id or "").strip()
    if "/" not in raw:
        return raw
    head, rest = raw.split("/", 1)
    if head in ("cohere", "co"):
        return rest
    return raw


def lookup_limits(
    model_id: str,
    account_type: str | None = None,
) -> dict[str, int]:
    table = CohereConfig().RATE_LIMITS
    plan = _plan(account_type)
    key = f"{plan}/{_strip_prefix(model_id)}"
    if key in table:
        return dict(table[key])
    return {}
```

- [ ] **Step 2: Implement `_item`, summary, detail builders**

`_item` must match Alibaba: `total=0` ⇒ `unlimited=True`,
`remaining` computed.

`summary_quota_rows`:

1. Always: `requests (last 60s)`, `tokens (last 60s)` unlimited
   from aggregated `minute_by_model`.
2. If `_plan(account_type) == "free"`: add
   `calls (month)` with `used=month_used`, `total=1000`
   from `RATE_LIMITS["free/_monthly"]["calls"]`.

`apply_local_usage(account_type, minute_by_model, …)`:

- For every `RATE_LIMITS` key starting with `f"{plan}/"` where the
  suffix is **not** `_monthly`, `rerank`, or `embed`: emit
  `{model} requests (RPM)` with local last-minute request count.
- Also emit endpoint rows:
  - `{plan}/rerank` → `rerank requests (RPM)`
  - `{plan}/embed` → `embed inputs (IPM)` using local request
    count as a proxy for inputs if no better signal (document in
    FLOW.md).

Do **not** include `_monthly` in detail rows (it belongs on the
summary card only).

- [ ] **Step 3: Local usage queries**

Copy the Alibaba pattern: query `UsageHistory` where
`provider` matches `cohere` (case-insensitive) and connection id
hyphen-insensitive. Aggregate last 60s by model for RPM bars;
for monthly calls on `free`, count rows since UTC month start
for that connection (all models).

- [ ] **Step 4: Header helpers + observe**

`quotas_from_headers`: if limit/remaining request headers exist,
build last-model RPM row(s) using config totals when header limit
missing. Return `[]` if nothing useful.

`observe_response`: no-op when no live remaining header. Otherwise
merge into cache **summary-only** (keep `last 60s` / `calls (month)`
bars; replace or append last-model live RPM). Never write the full
published catalog into `quota_cache`.

- [ ] **Step 5: Handler class**

```python
class CohereUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "cohere"
    USES_UPSTREAM = False

    async def fetch(...) -> UsageResponse:
        # plan label = accountType
        # rows = summary_quota_rows(...)
        # message explains Model details for per-model RPM

    async def fetch_model_details(...) -> UsageResponse:
        # rows = apply_local_usage(...)  # NOT cached by router

    async def observe_response(...):
        # summary-safe merge only
```

Read `accountType` from `provider_data` in `fetch` /
`fetch_model_details` (router already passes connection data).
Default `"free"`.

- [ ] **Step 6: Import check**

```bash
cd backend && ../.venv-local/bin/python -c \
  "from app.services.quota import get_usage_handler; \
   h=get_usage_handler('cohere'); \
   assert h is not None; print(h.PROVIDER_ID, h.USES_UPSTREAM)"
```

Expected: `cohere False`

---

### Task 3: Unit tests

**Files:**
- Modify: `backend/tests/test_quota_handlers.py`

**Interfaces:**
- Consumes: helpers/handler from Task 2

- [ ] **Step 1: Add imports + registry assert**

```python
from app.providers.cohere.quota import (
    CohereUsageHandler,
    apply_local_usage as co_apply_local_usage,
    lookup_limits as co_lookup_limits,
    quotas_from_headers as co_quotas_from_headers,
    summary_quota_rows as co_summary_quota_rows,
)
```

In `test_supported_providers`, add:
`assert "cohere" in providers`

- [ ] **Step 2: Write tests**

```python
def test_cohere_handler_registered() -> None:
    handler = get_usage_handler("cohere")
    assert handler is not None
    assert isinstance(handler, CohereUsageHandler)


def test_cohere_config_limits() -> None:
    assert co_lookup_limits("command-r", "free")["rpm"] == 20
    assert co_lookup_limits("co/command-r", "payg")["rpm"] == 500
    assert co_lookup_limits(
        "command-a-reasoning", "payg",
    )["rpm"] == 20
    assert co_lookup_limits("rerank", "free")["rpm"] == 10
    assert co_lookup_limits("unknown", "free") == {}


def test_cohere_summary_rows_free() -> None:
    rows = co_summary_quota_rows(
        {"command-r": {"tokens": 100, "requests": 2}},
        month_used=40,
        account_type="free",
    )
    by_name = {r["name"]: r for r in rows}
    assert by_name["requests (last 60s)"]["used"] == 2
    assert by_name["tokens (last 60s)"]["used"] == 100
    assert by_name["calls (month)"]["used"] == 40
    assert by_name["calls (month)"]["total"] == 1000


def test_cohere_summary_rows_payg_no_monthly() -> None:
    rows = co_summary_quota_rows(
        {"command-r": {"tokens": 1, "requests": 1}},
        month_used=999,
        account_type="payg",
    )
    names = {r["name"] for r in rows}
    assert "calls (month)" not in names
    assert len(rows) == 2


def test_cohere_local_usage_detail() -> None:
    rows = co_apply_local_usage(
        "free",
        {"command-r": {"tokens": 0, "requests": 3}},
    )
    rpm = next(
        r for r in rows
        if r["name"].startswith("command-r")
        and "RPM" in r["name"]
    )
    assert rpm["used"] == 3
    assert rpm["total"] == 20


def test_cohere_quotas_from_headers() -> None:
    headers = {
        "x-ratelimit-limit-requests": "20",
        "x-ratelimit-remaining-requests": "17",
    }
    rows = co_quotas_from_headers(
        headers, "command-r", "free",
    )
    assert rows
    assert rows[0]["used"] == 3
    assert rows[0]["total"] == 20
```

- [ ] **Step 3: Run tests**

```bash
cd backend && ../.venv-local/bin/pytest \
  tests/test_quota_handlers.py -k cohere -v
```

Expected: all selected tests PASS.

---

### Task 4: Quota Tracker UI gate

**Files:**
- Modify: `frontend/src/pages/QuotaTrackerPage.jsx`
  (around the `showModelDetails` line)

**Interfaces:**
- Consumes: existing `GET /usage/{id}?detail=models` path
- Produces: ListTree button visible for `cohere` and `alims-intl`

- [ ] **Step 1: Extend the gate**

Replace:

```javascript
const showModelDetails = provider.provider === 'alims-intl'
```

with:

```javascript
const showModelDetails = (
  provider.provider === 'alims-intl'
  || provider.provider === 'cohere'
)
```

Keep line length ≤ 80 where practical (break as above).

- [ ] **Step 2: Manual check note**

In running app: Quota Tracker → Cohere connection → ListTree opens
modal and calls `GET /usage/{id}?detail=models`. No code change to
`quota.js` required (comment already mentions alims; optionally
update comment to include cohere).

---

### Task 5: FLOW.md + final verification

**Files:**
- Create: `backend/app/providers/cohere/FLOW.md`

**Interfaces:**
- Produces: provider-local flow doc (English) matching implemented
  files only — no shared template dump.

- [ ] **Step 1: Write FLOW.md**

Sections (mirror Groq/Alibaba Studio length):

1. One-paragraph overview (compat base URL, trial/prod via
   `accountType`, per-model Chat RPM + monthly free cap)
2. Files table
3. Constants (`PROVIDER_ID`, `ALIAS`, `BASE_URL`,
   `MODEL_CATALOG_TABLE`, auth)
4. Proxy chat entry diagram
5. Models / catalog
6. Quota: summary vs `detail=models`, monthly free bar, observe
7. Rerank native note (`handler.execute_rerank`)
8. Implementation notes (`co/` strip, payg≡subscribe caps)

- [ ] **Step 2: Full Cohere-related pytest**

```bash
cd backend && ../.venv-local/bin/pytest \
  tests/test_quota_handlers.py -k cohere -v
```

Expected: PASS.

- [ ] **Step 3: Confirm catalog flag in process**

```bash
cd backend && ../.venv-local/bin/python -c \
  "from app.providers.provider import Provider; \
   p=Provider('cohere'); \
   assert p.config().MODEL_CATALOG_TABLE; \
   print('catalog', p.config().MODEL_CATALOG_TABLE)"
```

- [ ] **Step 4: Stop — ask user before commit**

Report: config + quota + tests + UI gate + FLOW.md done.
Do not commit unless requested.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| `MODEL_CATALOG_TABLE` | 1 |
| `RATE_LIMITS` + notice | 1 |
| Catalog slice doc update | 1 |
| `accountType` free/payg/subscribe | 2 |
| free monthly 1000 | 2, 3 |
| Summary fetch (no fat cache) | 2 |
| `fetch_model_details` | 2 |
| observe summary-safe | 2 |
| Auto registry via `quota.py` | 2 |
| Unit tests | 3 |
| QuotaTracker ListTree for cohere | 4 |
| `FLOW.md` | 5 |
| No new DB columns / no blob catalog writes | Global |

## Placeholder / consistency self-review

- No TBD steps; RATE_LIMITS key names fixed in Task 1.
- `subscribe` mirrors `payg` explicitly.
- Handler id is `cohere` everywhere (folder `cohere`, not hyphen).
- UI gate uses provider id `cohere`.
