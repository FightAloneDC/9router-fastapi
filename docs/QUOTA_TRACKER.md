# Quota Tracker — Mechanism & Flow Documentation

## Overview

The Quota Tracker monitors API usage limits for provider connections. Each provider (GitHub, Claude, Codex, Kiro, etc.) has its own usage API that returns quota data. The system fetches this data per-connection and displays it in a unified dashboard.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                  │
│                                                                  │
│  QuotaTrackerPage                                                │
│    ├── fetchData() ─────────── GET /quota ──────────┐           │
│    ├── auto-refresh (30s/60s/180s)                  │           │
│    ├── localStorage cache (5 min TTL)               │           │
│    └── per-connection refresh ── GET /usage/{id} ──┐│           │
│                                                     ││           │
└─────────────────────────────────────────────────────┘│───────────┘
                                                       │
┌──────────────────────────────────────────────────────┘│───────────┐
│                        Backend                         │           │
│                                                        │           │
│  GET /quota                                            │           │
│    └── List all connections (DB)                       │           │
│        └── Return: { id, provider, name, is_active,   │           │
│                       quotas: [], plan: null }         │           │
│                                                        │           │
│  GET /usage/{connectionId}                             │           │
│    ├── 1. Get connection from DB                       │           │
│    ├── 2. Refresh OAuth token (if needed)              │           │
│    ├── 3. Call provider-specific usage handler ────────┘           │
│    └── 4. Return standardized quota data                          │
│                                                                    │
│  Usage Handlers (per provider):                                    │
│    ├── getGitHubUsage(accessToken)                                │
│    ├── getClaudeUsage(accessToken)                                │
│    ├── getCodexUsage(accessToken)                                 │
│    ├── getKiroUsage(accessToken, providerSpecificData)            │
│    ├── getQoderUsage(accessToken)                                 │
│    └── ... (15+ providers)                                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Initial Page Load

```
User opens /quota-tracker
    │
    ├── Frontend checks localStorage cache
    │   ├── Cache hit (< 5 min) → Show cached data immediately
    │   └── Cache miss → Show loading skeleton
    │
    ├── Frontend calls GET /quota
    │   └── Backend returns all connections with empty quotas
    │
    ├── Frontend displays connection cards (no quota data yet)
    │
    └── Frontend calls GET /usage/{id} for each connection
        └── Backend fetches real quota from provider API
            └── Frontend updates cards with quota data
```

### 2. Per-Connection Quota Fetch

```
Frontend: GET /usage/{connectionId}
    │
    ▼
Backend: /api/usage/[connectionId]/route.js
    │
    ├── 1. Get connection from DB
    │      └── Validate: must be OAuth or whitelisted apikey provider
    │
    ├── 2. Refresh OAuth credentials (if expired)
    │      └── executor.refreshCredentials(credentials)
    │      └── Update DB with new tokens
    │
    ├── 3. Call provider-specific usage handler
    │      │
    │      ├── USAGE_HANDLERS[provider](connection)
    │      │
    │      ├── GitHub: GET copilot_internal/user
    │      │   └── Returns: { plan, quotas: { chat, completions, premium } }
    │      │
    │      ├── Claude: GET /v1/organizations/{org}/usage
    │      │   └── Returns: { plan, quotas: { "session (5h)", "weekly (7d)" } }
    │      │
    │      ├── Codex: GET /v1/usage
    │      │   └── Returns: { plan, quotas: { session, weekly, review_session, review_weekly } }
    │      │
    │      ├── Kiro: GET CodeWhisperer/GetUsageLimits
    │      │   └── Returns: { plan, quotas: { agentic_request, ... } }
    │      │
    │      └── Qoder: GET /v1/user/usage
    │          └── Returns: { quotas: { user, organization } }
    │
    └── 4. Return standardized response
           {
             plan: "Pro",
             quotas: {
               "session": { used: 45, total: 100, remaining: 55, resetAt: "..." },
               "weekly": { used: 200, total: 1000, remaining: 800, resetAt: "..." }
             }
           }
```

### 3. Frontend Data Normalization

Each provider returns different quota shapes. The frontend normalizes them:

```javascript
// GitHub returns:
{ quotas: { chat: { used, total, resetAt }, completions: {...} } }

// Claude returns:
{ quotas: { "session (5h)": { used, total, resetAt }, "weekly (7d)": {...} } }

// Codex returns:
{ quotas: { session: { used, total, resetAt }, weekly: {...} } }

// All normalized to:
[{ name: "session", used: 45, total: 100, resetAt: "2026-06-27T15:00:00Z" }]
```

### 4. Auto-Refresh Cycle

```
┌─────────────────────────────────────────────┐
│  Auto-Refresh Loop (every 30s/60s/180s)     │
│                                              │
│  1. Check tab visibility                     │
│     └── If tab hidden → pause, skip refresh  │
│                                              │
│  2. Fetch fresh data                         │
│     └── GET /quota → update all connections  │
│                                              │
│  3. Update localStorage cache                │
│     └── setQuotaCache(data)                  │
│                                              │
│  4. Reset countdown timer                    │
│     └── setCountdown(refreshInterval)        │
│                                              │
└─────────────────────────────────────────────┘
```

## Provider-Specific Usage APIs

### GitHub Copilot
```
Endpoint: GET https://api.github.com/copilot_internal/user
Auth: GitHub OAuth token (not copilotToken)
Headers: Authorization: token {accessToken}

Response (Paid):
{
  "copilot_plan": "individual",
  "quota_snapshots": {
    "chat": { "entitlement": 1500, "remaining": 1200, "unlimited": false },
    "completions": { "entitlement": 3000, "remaining": 2800 },
    "premium_interactions": { "entitlement": 300, "remaining": 250 }
  },
  "quota_reset_date": "2026-07-01T00:00:00Z"
}

Response (Free):
{
  "monthly_quotas": { "chat": 50, "completions": 2000 },
  "limited_user_quotas": { "chat": 10, "completions": 500 },
  "limited_user_reset_date": "2026-07-01T00:00:00Z"
}
```

### Claude (Anthropic)
```
Endpoint (OAuth): GET https://api.anthropic.com/v1/usage
Auth: OAuth Bearer token
Headers: anthropic-beta: oauth-2025-04-20

Response:
{
  "five_hour": { "utilization": 45, "resets_at": 1719500000 },
  "seven_day": { "utilization": 23, "resets_at": 1719900000 },
  "seven_day_sonnet": { "utilization": 30 },
  "seven_day_opus": { "utilization": 15 }
}

utilization = % USED (e.g. 45 means 45% used, 55% remaining)
```

### Codex (OpenAI)
```
Endpoint: GET https://api.openai.com/v1/usage
Auth: OAuth Bearer token

Response:
{
  "plan_type": "pro",
  "rate_limit": {
    "primary_window": { "used_percent": 35, "reset_at": "..." },
    "secondary_window": { "used_percent": 12, "reset_at": "..." }
  },
  "rate_limit_reset_credits": { "available_count": 2 }
}
```

### Kiro (AWS CodeWhisperer)
```
Endpoint: GET https://codewhisperer.us-east-1.amazonaws.com/getUsageLimits
Auth: OAuth Bearer token or API Key
Headers: x-amz-user-agent: aws-sdk-js/1.0.0 KiroIDE

Response:
{
  "subscriptionInfo": { "subscriptionTitle": "Kiro Pro" },
  "usageBreakdownList": [
    {
      "resourceType": "AGENTIC_REQUEST",
      "currentUsageWithPrecision": 150,
      "usageLimitWithPrecision": 1000,
      "nextDateReset": "2026-07-01T00:00:00Z",
      "freeTrialInfo": { ... }
    }
  ]
}
```

### Qoder
```
Endpoint: GET https://api.qoder.dev/v1/user/usage
Auth: OAuth Bearer token

Response:
{
  "quotas": {
    "user": { "total": 1000, "used": 350, "remaining": 650, "unit": "credits", "resetAt": "..." },
    "organization": { "total": 5000, "used": 1200, "remaining": 3800 }
  }
}
```

## Standardized Quota Schema

All providers return data normalized to this shape:

```typescript
interface QuotaItem {
  name: string;           // "session", "weekly", "chat", "completions", etc.
  used: number;           // Usage count or percentage
  total: number;          // Total limit (0 = unlimited)
  remaining?: number;     // Remaining count (absolute)
  remainingPercentage?: number; // Remaining as 0-100%
  resetAt: string | null; // ISO 8601 reset timestamp
  unlimited?: boolean;    // True if no limit
}

interface UsageResponse {
  plan?: string;          // "Pro", "Individual", etc.
  quotas: Record<string, QuotaItem>;  // Named quota buckets
  message?: string;       // Error/info message if quota unavailable
  limitReached?: boolean; // Whether any limit is reached
}
```

## Supported Providers

| Provider | Auth Type | Usage Endpoint | Quotas Returned |
|----------|-----------|----------------|-----------------|
| GitHub | OAuth | copilot_internal/user | chat, completions, premium |
| Claude | OAuth | /v1/usage | session (5h), weekly (7d), per-model |
| Codex | OAuth | /v1/usage | session, weekly, review |
| Kiro | OAuth/API Key | CodeWhisperer GetUsageLimits | agentic_request, free_trial |
| Qoder | OAuth | /v1/user/usage | user, organization |
| Gemini CLI | OAuth | cloudresourcemanager | project quotas |
| Antigravity | OAuth | Vertex AI | per-model quotas |
| GLM/MiniMax | API Key | Provider API | model quotas |
| Qwen | OAuth | DashScope | token quotas |
| iFlow | OAuth | Provider API | usage data |
| CodeBuddy CN | OAuth | Provider API | usage data |

## Caching Strategy

### Frontend Cache (localStorage)
```
Key: "quotaCacheData"
TTL: 5 minutes
Format: { data: [...], timestamp: Date.now() }

Flow:
1. Page load → check cache
2. Cache hit (< 5 min) → show cached data immediately
3. Fetch fresh data in background
4. Update cache with fresh data
5. On error → fall back to cache if available
```

### Rate Limit Protection
```
Claude OAuth usage endpoint has 429 rate limiting.
Solution: 180s cooldown per token after 429.

Code:
if (Date.now() < cooldownUntil) {
  return getClaudeUsageLegacy(accessToken);  // Fallback to legacy endpoint
}
```

## Frontend Features

### Filtering & Sorting
- **Provider filter**: Filter by provider type (GitHub, Claude, etc.)
- **Status filter**: All / Active / Inactive connections
- **Sort mode**: Default / % Low→High / % High→Low
- **Expiring first**: Sort by earliest reset time
- **Search**: Filter by connection name

### Connection Management
- **Toggle active/inactive**: Enable/disable connection (PATCH /providers/{id})
- **Edit name**: Update connection display name
- **Delete**: Remove connection with confirmation
- **Bulk actions**: Disable depleted (≤5%), Enable all inactive

### Display Features
- **Emoji indicators**: 🟢 (>70%), 🟡 (30-70%), 🔴 (<30%)
- **Table-based layout**: Compact per-provider quota table
- **Reset time**: "Today, 12:00 PM" / "Tomorrow, 3:00 PM" format
- **Provider logos**: PNG from `/providers/{id}.png`
- **Pagination**: 10/20/50 per page

## Implementation Plan (FastAPI)

### Phase 1: Backend Usage Service
```
backend/app/services/quota/
├── __init__.py           # Usage handler registry
├── base.py              # BaseUsageHandler abstract class
├── github.py            # GitHub Copilot usage
├── claude.py            # Claude usage (OAuth + legacy)
├── codex.py             # Codex usage
├── kiro.py              # Kiro usage
├── qoder.py             # Qoder usage
└── shared.py            # Common helpers (parseResetTime, etc.)
```

### Phase 2: API Endpoint
```python
# backend/app/routers/quota.py
@router.get("/usage/{connection_id}")
async def get_usage(connection_id: str, db = Depends(get_db)):
    conn = await get_connection(db, connection_id)
    handler = get_usage_handler(conn.provider)
    usage = await handler.fetch(conn.access_token, conn.provider_specific_data)
    return usage
```

### Phase 3: Frontend Integration
- Update `QuotaTrackerPage` to fetch per-connection usage
- Add loading/error states per connection card
- Implement `parseQuotaData` normalizer

## Key Files Reference

### Node.js (Reference)
```
open-sse/services/usage.js           # Handler registry
open-sse/services/usage/github.js    # GitHub handler
open-sse/services/usage/claude.js    # Claude handler
open-sse/services/usage/codex.js     # Codex handler
open-sse/services/usage/kiro.js      # Kiro handler
open-sse/services/usage/shared.js    # Shared helpers

src/app/api/usage/[connectionId]/route.js  # API endpoint
src/app/(dashboard)/dashboard/usage/components/ProviderLimits/
├── index.js           # Main component
├── utils.js           # parseQuotaData, cache helpers
├── QuotaTable.js      # Table display
└── QuotaProgressBar.js # Progress bar
```

### FastAPI (Current)
```
backend/app/routers/quota.py              # Placeholder endpoint
frontend/src/pages/QuotaTrackerPage.jsx   # UI component
frontend/src/api/quota.js                 # API client
```
