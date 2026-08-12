# Design: Connection Last Error Display

**Date:** 2026-08-12  
**Status:** Approved for planning (pending user review of this file)  
**Scope:** `/providers/:id` connection rows — human-readable last error + copyable full detail

## Problem

There is no good way to see why a connection last failed. The official UI
shows truncated raw JSON before the priority number (noisy, hard to scan)
and relies on hover for a slightly longer truncation (poor on mobile).

`lastError` is usually a raw upstream body or exception string (providers
differ). That content is for debugging, not for an inline list label.

## Goals

- From the list, quickly understand **why** the connection failed.
- Open full raw error on demand and **copy** it when needed.
- Keep the connection list scannable (no raw JSON in the badge row).

## Non-goals

- Per-provider error parsers in frontend or routers (PS Rule).
- New DB columns.
- Changing how the backend writes `lastError` / `lastErrorAt`.
- Hover-only as the sole detail path.

## Decision

**Approach:** Human short summary on the row + click-to-open detail with
full text and Copy (approach #1 from brainstorming).

## UI

### Connection row (only if `lastError` is non-empty)

- Secondary line under the badge row (not beside `#priority`):
  muted/danger-tinted text, ~72 characters max + ellipsis.
- Optional relative time from `lastErrorAt` (e.g. `2h ago`) when present.
- Click summary or a small info control → detail surface.
- If connection is inactive/disabled but still has `lastError`, still show
  the summary (useful context for last failure).

### Detail (popover on desktop; small modal/drawer on mobile)

- Title: `Last error`
- Absolute `lastErrorAt` when present
- Same human summary as the list
- Full raw `lastError` in scrollable monospace block
- **Copy full error** button
- Dismiss: outside click / Escape

### Badges

- Existing status badges (`error`, Refresh Error, Token Expired, etc.)
  stay as quick signals.
- Summary line answers **why**; it does not replace badges.
- Do not put long error text into badges.

## Summary extraction (generic, ordered)

Frontend helper (e.g. `summarizeLastError(raw: string): string`):

1. Try `JSON.parse`; if object, prefer string fields in order:
   `error.message`, `message`, `error` (if string), `detail` (if string).
2. Else strip crude HTML tags; take first line / first sentence.
3. Fallback: truncate raw string at a word boundary (~72 chars).
4. If an HTTP status is detectable at the start (`429: …`, `HTTP 503`),
   keep it as a short prefix when helpful.

No provider-specific branches.

## Data

Existing fields only (already on connection payload):

| Field | Use |
|-------|-----|
| `lastError` | Raw body for detail + copy; input to summarizer |
| `lastErrorAt` | Relative on row; absolute in detail |
| `test_status` | Existing badge logic unchanged |

Clearing `lastError` on successful test / backend clear removes the UI.

## Scope (v1)

- `ConnectionRow` on `ProviderDetailPage` (+ small shared util for summarize).
- No backend API changes required for v1.

## Success criteria

1. Failed connections show a readable one-line reason without hover.
2. JSON-heavy upstream bodies still yield a useful summary when possible.
3. User can open detail and copy the full raw `lastError`.
4. List remains free of truncated raw JSON next to priority.
