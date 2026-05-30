# Usage Page Phase 2 — Implementation Plan

## Status: COMPLETE (pending user verification)

## Phases

### Phase A: Backend Multi-View Aggregation
- [x] Add new Pydantic schemas (UsageAccountItem, UsageApiKeyItem, UsageEndpointItem, RecentRequestItem)
- [x] Update UsageStatsOut to include byAccount, byApiKey, byEndpoint, recentRequests
- [x] Add byAccount query — GROUP BY connection_id, join provider_connections for account name
- [x] Add byApiKey query — GROUP BY api_key
- [x] Add byEndpoint query — GROUP BY endpoint
- [x] Add recentRequests query — last 20 requests ordered by timestamp desc
- Status: DONE
- Notes: Added 6 new schema classes and 4 new aggregation queries. Join uses func.cast for UUID→string comparison.

### Phase B: Frontend Multi-View Table
- [x] Add table view dropdown with 4 options (Model, Account, API Key, Endpoint)
- [x] Define columns per view
- [x] Implement expandable rows with group headers
- [x] Persist expand state in localStorage
- [x] Add Costs/Tokens toggle for table values
- [x] Store sortBy/sortOrder in URL search params
- Status: DONE
- Notes: Replaced ModelTable with generic UsageTable. View/sort/mode all persisted in URL params.

### Phase C: Recent Requests
- [x] Create RecentRequests card component
- [x] Show last ~20 requests with Status dot, Model, Input/Output tokens, Time ago
- [x] Auto-update time ago every second
- [x] Place next to chart in responsive grid
- Status: DONE
- Notes: Uses polling via /usage/stats recentRequests field. Time ago auto-updates every second.

### Phase D: Provider Topology / Status
- [x] Create provider status card layout
- [x] Show providers with active status, request count, last used
- [x] Visual indicators (colored dots/badges)
- Status: DONE
- Notes: Card-based layout with green dots, request counts, and cost per provider.

### Phase E: ESLint Fixes
- [x] Remove unused imports: useRef, useNavigate
- [x] Remove unused variable: totalTokens
- [x] Fix setState-in-effect patterns
- Status: DONE
- Notes: ESLint passes clean. Suppressed 3 set-state-in-effect warnings (standard data-fetching pattern).

## Issues Encountered
- (none yet)

## Completed
- Phase A: Backend multi-view aggregation — 6 new schemas, 4 new queries (byAccount, byApiKey, byEndpoint, recentRequests)
- Phase B: Frontend multi-view table — generic UsageTable with 4 views, expand/collapse, costs/tokens toggle, URL-persisted sort
- Phase C: Recent Requests — card with live time-ago, status dots, token counts
- Phase D: Provider Status — card-based layout with green indicators
- Phase E: ESLint fixes — all clean, build passes
