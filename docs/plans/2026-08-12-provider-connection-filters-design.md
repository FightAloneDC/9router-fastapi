# Design: Provider Detail Connection Filters

**Date:** 2026-08-12  
**Status:** Approved for planning (pending user review of this file)  
**Scope:** `/providers/:id` connection list — server-side search + filters with pagination

## Problem

Connection lists are paginated server-side, but there is no search or
status filter. Finding error / inactive accounts requires flipping pages.
Client-side filtering cannot see rows outside the current page.

## Goals

- Filter and search connections **with** pagination (one request).
- Make error / inactive / token / cooldown accounts easy to find.
- Keep select-all / bulk ops scoped to the **filtered** set.
- Show both filtered count and unfiltered total in the footer.

## Non-goals

- Migrating legacy `displayName` values (import already fixed).
- Client-side-only filtering of the current page.
- Changing priority / round-robin semantics (handled separately).

## Decisions (from brainstorming)

| Topic | Choice |
|-------|--------|
| Approach | Extend existing paginated endpoint (server-side) |
| Filter combine | **AND** across all dimensions |
| Search fields | `name`, `email`, `data.displayName` only (no id) |
| Select all / bulk | Filtered set only |
| Counts | `total` = filtered; `total_all` = unfiltered |

## API

### Endpoint

`GET /providers/by-provider/{provider_id}/connections`

Existing query params unchanged: `page`, `page_size`,
`include_models`, `include_ids`.

### New optional query params (all AND)

| Param | Type | Behavior |
|-------|------|----------|
| `q` | string | Case-insensitive match on `name`, `email`, or JSON `displayName`. Trimmed; empty ignored |
| `is_active` | bool | Column `is_active` |
| `test_status` | string | Match JSON `testStatus` (e.g. `connected`, `error`, `expired`, `unavailable`, `untested`, `unknown`). Treat `success` / `active` as aliases of connected where useful for UI |
| `auth_type` | string | `oauth` \| `apikey` (DB column) |
| `has_proxy` | bool | `proxy_pool_id` null / not null |
| `proxy_pool_id` | UUID | Specific pool; AND with other filters |
| `token_issue` | enum | `expired` \| `refresh_error` \| `any` — from OAuth JSON (`expiresAt`, `lastError`) |
| `in_cooldown` | bool | Any `modelLock_*` JSON key with future timestamp |

### Response additions

| Field | Meaning |
|-------|---------|
| `total` | Count after filters (pagination + `connectionIds`) |
| `total_all` | Count for provider with **no** list filters |

`connectionIds` (when `include_ids=true`) must use the **same** filter
predicate as `items` / `total`.

Changing filters resets client `page` to `1`.

## UI (`ProviderDetailPage`)

Filter bar above the connection list (before “This page” checkbox):

1. Search input — debounce ~300ms; placeholder `Search name or email…`
2. Active — All / Active / Inactive
3. Status — All + relevant `test_status` values
4. Auth — All / OAuth / API key (hide if provider is single-auth)
5. Proxy — All / With proxy / No proxy (+ optional pool select)
6. Token — All / Expired / Refresh error / Any issue (OAuth only)
7. Cooldown — All / In cooldown / Not in cooldown
8. Clear filters — when any filter is active

### Copy / empty states

- Header connection count uses **`total_all`**.
- Footer:
  - No filter: `1–10 of 413`
  - Filtered: `1–10 of 47 · filtered from 413`
- No matches: “No connections match filters” + Clear filters  
  (distinct from “No connections yet”).
- **Select All (N)** uses filtered `total`; label may read  
  `Select All filtered (N)`.

## Implementation notes

- Prefer SQL/JSON predicates in Postgres so pagination stays correct.
- Reuse one shared “filter where” builder for count, page, and ids.
- Frontend: pass filter state into `providersApi` list params; reset page
  on filter change.
- Do not expand scope to unrelated ProviderDetail refactors.

## Success criteria

1. With 100+ connections, filtering `test_status=error` returns only
   errors across pages; footer shows filtered + `total_all`.
2. Search by email finds the account even if not on page 1.
3. Select All + bulk delete only affects filtered connections.
4. Clearing filters restores full list and `total === total_all`.
