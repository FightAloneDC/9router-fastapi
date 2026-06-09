# Usage Menu Investigation Report

**Date:** 2026-05-30
**Investigator:** Claude Code
**Status:** Complete

---

## Executive Summary

Backend tracking untuk semua endpoint proxy `/v1/` **SUDAH ADA** dan berfungsi. Issues yang dilaporkan terutama disebabkan oleh:
1. **Data source mismatch** — Recent Requests dan Details menggunakan tabel berbeda
2. **SSE disabled** — Real-time updates untuk canvas edges tidak aktif
3. **No active request tracking** — Tidak ada mechanism untuk live request events

---

## 1. Backend Tracking Architecture

### 1.1 Tracked Endpoints

| Endpoint | File | Streaming | Non-Streaming |
|----------|------|-----------|---------------|
| `/v1/chat/completions` | `backend/app/routers/v1_proxy/chat.py` | ✅ | ✅ |
| `/v1/messages` | `backend/app/routers/v1_proxy/messages.py` | ✅ | ✅ |
| `/v1/responses` | `backend/app/routers/v1_proxy/responses.py` | ✅ | ✅ |
| `/v1/embeddings` | `backend/app/routers/v1_proxy/embeddings.py` | N/A | ✅ |

### 1.2 Database Tables

**`usage_history`** — Individual request records
- Fields: `id`, `timestamp`, `provider`, `model`, `connection_id`, `api_key`, `endpoint`, `prompt_tokens`, `completion_tokens`, `cost`, `status`, `tokens` (JSON), `meta` (JSON)
- Source: `backend/app/models/usage.py`

**`usage_daily`** — Aggregated daily statistics
- Fields: `date_key` (YYYY-MM-DD), `data` (JSON blob)
- JSON structure: `{ requests, promptTokens, completionTokens, cost, byProvider: {}, byModel: {} }`
- Source: `backend/app/models/usage.py`

**`request_details`** — Full request/response payloads
- Fields: `id`, `provider`, `model`, `connection_id`, `timestamp`, `status`, `latency_ttft`, `latency_total`, `prompt_tokens`, `completion_tokens`, `cost`, `request`, `provider_request`, `provider_response`, `response`
- Source: `backend/app/models/request_detail.py`
- Max records: 500 (auto-cleanup oldest)

### 1.3 Tracking Service

**File:** `backend/app/services/usage_tracking.py`

**Key Functions:**
- `save_request_usage()` — Saves to `usage_history` + upserts `usage_daily`
- `save_request_detail()` — Saves to `request_details`
- `_calculate_cost()` — Cost calculation based on model name
- `cleanup_old_details()` — Deletes oldest records if > 500

**Cost Calculation:**
- Uses `_COST_TABLE` with model prefix matching
- Default rate: $1/M input tokens, $2/M output tokens
- Table covers ~30 model prefixes (GPT, Claude, Gemini, DeepSeek, etc.)

### 1.4 API Endpoints

**File:** `backend/app/routers/usage.py`

| Endpoint | Description |
|----------|-------------|
| `GET /usage/stats` | Aggregated stats (by provider, model, account, endpoint, API key) |
| `GET /usage/chart` | Chart data points (daily/hourly) |
| `GET /usage/history` | Raw usage history with filters |
| `GET /usage/request-details` | Paginated request details |
| `GET /usage/request-detail/{id}` | Full request detail with payloads |
| `GET /usage/providers` | Unique provider names |
| `GET /usage/stream` | SSE for real-time updates |

---

## 2. Frontend Architecture

### 2.1 UsagePage.jsx

**File:** `frontend/src/pages/UsagePage.jsx`

**Tabs:**
1. **Overview** — Stat cards, topology, recent requests, chart, breakdown table
2. **Details** — Paginated request details with filters

**Components:**
- `StatCard` — Total requests, input tokens, output tokens, cost
- `ProviderTopology` — Canvas with provider nodes and edges
- `RecentRequests` — Last 20 requests table
- `UsageChart` — Area chart (tokens/cost)
- `UsageBreakdownTable` — By model/provider/account/endpoint
- `RequestDetailsTab` — Paginated details with drawer

### 2.2 ProviderTopology.jsx

**File:** `frontend/src/components/ProviderTopology.jsx`

**Props:**
- `providers` — Array of provider stats (from `stats.byProvider`)
- `activeRequests` — Array of active request objects
- `lastProvider` — Last used provider ID
- `errorProvider` — Last error provider ID

**Edge Animation:**
- `active` → Green (#4ade80), animated, strokeWidth 2.5
- `last` → Yellow (#fbbf24), static, strokeWidth 2
- `error` → Red (#f87171), static, strokeWidth 2.5
- Default → Gray (#71717a), static, strokeWidth 1.5

### 2.3 SSE (Real-time Updates)

**Backend:** `backend/app/routers/usage_stream.py`
- Endpoint: `GET /usage/stream`
- Event bus: In-memory `_subscribers` list
- `notify_usage_update()` — Called after each usage save

**Frontend:** **COMMENTED OUT** (lines 1205-1225 in UsagePage.jsx)
```javascript
// SSE for real-time updates (disabled — endpoint not yet implemented)
// useEffect(() => { ... })
```

---

## 3. Issues Found

### 3.1 Issue #1: Recent Requests Data Source Mismatch

**Symptom:** Recent Requests table shows different data than Details tab

**Root Cause:**
- Recent Requests queries from `usage_history` table (line 305-328 in usage.py)
- Details tab queries from `request_details` table (line 480-562 in usage.py)
- These are **SEPARATE tables** with no linkage

**Data Differences:**
| Field | `usage_history` | `request_details` |
|-------|-----------------|-------------------|
| ID | Auto-increment | Auto-increment |
| Timestamp | ✅ | ✅ |
| Provider | ✅ | ✅ |
| Model | ✅ | ✅ |
| Tokens | ✅ | ✅ |
| Cost | ✅ | ✅ |
| Request/Response | ❌ | ✅ |
| Latency | ❌ | ✅ |

**Impact:**
- Recent Requests shows aggregated data (no request/response payloads)
- Details shows per-request data (with payloads)
- Records may appear in one but not the other if tracking fails partially

### 3.2 Issue #2: Canvas Edges No Live Events

**Symptom:** Edges on canvas don't animate when requests are active

**Root Cause:**
1. **SSE disabled in frontend** — Code is commented out
2. **No active request tracking** — Backend doesn't track "in-flight" requests
3. **ProviderTopology not connected** — UsagePage doesn't pass `activeRequests` prop

**Current UsagePage.jsx line 1283:**
```jsx
<ProviderTopology providers={stats?.byProvider || []} />
```
Missing props: `activeRequests`, `lastProvider`, `errorProvider`

### 3.3 Issue #3: Token Usage & Cost Tracking

**Symptom:** Tracking "belum terintegrasi dengan benar"

**Analysis:**
- Backend tracking IS working (confirmed by code review)
- Cost calculation uses `_COST_TABLE` with ~30 model prefixes
- Default rate is conservative ($1/M input, $2/M output)

**Potential Issues:**
1. **Incomplete cost table** — Many models not covered
2. **No custom rates** — Can't override per provider/model
3. **Streaming usage capture** — Depends on provider sending `usage` in final SSE chunk
4. **Qoder special handling** — SSE unwrapping may miss usage data

### 3.4 Issue #4: Data Synchronization

**Symptom:** Records not synced between Recent Requests and Details

**Root Cause:**
- `save_request_usage()` and `save_request_detail()` are called separately
- If one fails, the other may succeed (partial tracking)
- No transaction wrapping both saves

**Code Evidence (chat.py lines 130-156):**
```python
await save_request_usage(db, ...)  # Saves to usage_history
notify_usage_update()
await save_request_detail(db, ...)  # Saves to request_details
```
These are separate calls — if `save_request_detail` fails, `usage_history` still has the record.

---

## 4. Reference: Original 9Router (Node.js)

**Canvas Edge Animation:**
- Original 9Router Node.js has real-time edge animation
- Uses WebSocket or SSE to push active request events
- Edges light up when provider is handling requests

**Data Model:**
- Original uses single table for all request data
- No separation between usage history and request details

---

## 5. Recommendations

### Priority 1: Fix Recent Requests Data Source
- Query Recent Requests from `request_details` instead of `usage_history`
- Or add `request_detail_id` foreign key to `usage_history`

### Priority 2: Enable SSE + Active Request Tracking
- Uncomment SSE code in UsagePage.jsx
- Add active request tracking in backend (in-memory set)
- Pass `activeRequests` prop to ProviderTopology

### Priority 3: Improve Cost Tracking
- Expand `_COST_TABLE` with more models
- Add custom cost rate configuration
- Handle streaming usage capture edge cases

### Priority 4: Data Consistency
- Wrap `save_request_usage` + `save_request_detail` in single transaction
- Add retry logic for failed saves
- Add data validation before save

---

## 6. Files Reference

### Backend
- `backend/app/models/usage.py` — UsageHistory, UsageDaily models
- `backend/app/models/request_detail.py` — RequestDetail model
- `backend/app/routers/usage.py` — Usage API endpoints
- `backend/app/routers/usage_stream.py` — SSE endpoint
- `backend/app/services/usage_tracking.py` — Tracking service
- `backend/app/routers/v1_proxy/chat.py` — Chat completions proxy
- `backend/app/routers/v1_proxy/messages.py` — Messages proxy
- `backend/app/routers/v1_proxy/responses.py` — Responses proxy
- `backend/app/routers/v1_proxy/embeddings.py` — Embeddings proxy
- `backend/app/routers/v1_proxy/shared.py` — Shared helpers

### Frontend
- `frontend/src/pages/UsagePage.jsx` — Usage page
- `frontend/src/components/ProviderTopology.jsx` — Canvas topology
- `frontend/src/api/usage.js` — Usage API client
