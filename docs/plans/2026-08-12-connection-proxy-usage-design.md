# Design: Connection Proxy Usage Modes

**Date:** 2026-08-12  
**Status:** Approved (user)  
**Scope:** Wire `proxy_pool_id` into real outbound HTTP with per-connection
usage modes; pool-level default template + mass apply.

## Problem

Apply Proxy only persists `proxy_pool_id` on connections. Test connection,
bulk test, OAuth refresh, and `/v1/*` upstream clients create
`httpx.AsyncClient` without `proxy=`, so assigned pools have no effect.

## Goals

- Per-connection **proxy usage mode**: Off / Selective (diagnostics) / All
  upstream.
- Selective checklist: test connection, test model, test chat, OAuth refresh.
- Pool page: **default template** + **Apply usage settings to all connections
  using this pool**.
- Diagnostics (Selective) must not force Cursor/CLI `/v1/*` through the proxy
  unless mode is **All**.

## Non-goals (v1)

- Multi-URL rotation inside one pool.
- Changing Settings global `outboundProxy*` (remains separate).
- Unifying Apply Proxy selection with bulk Enable/Disable/Test selection.
- Job cancel / Redis job store.

## Decisions

| Topic | Choice |
|-------|--------|
| UI model | Hybrid: radio Off / Selective / All; Selective shows checklist |
| Mass config | Pool default template + push button to connections on that pool |
| Chat vs production | Selective `testChat` = Chat UI only (tagged purpose); production `/v1/*` only when **All** |
| Storage (connections) | `data` JSON blob key `proxyUsage` — no new provider columns |
| Outbound wiring | Central factory `create_upstream_client(conn, purpose, ...)` |

## Data model

### Connection (`provider_connections.data`)

```json
"proxyUsage": {
  "mode": "off" | "selective" | "all",
  "flags": {
    "testConnection": false,
    "testModel": false,
    "testChat": false,
    "oauthRefresh": false
  }
}
```

Defaults when missing: `mode: "off"`, all flags `false`.  
New connection with a pool: copy pool template if present, else `off`.

### Proxy pool

Store the same shape as default template (preferred: JSON column
`default_proxy_usage` on `proxy_pools`, Alembic migration allowed — this is
not a provider-connection table).

Fields meaning: defaults for Apply Proxy / new binds / mass push — not a
live override of connection settings until the user clicks mass apply.

## UI

### `/providers/:id`

- Connection row / edit / Apply Proxy flow: choose pool + usage radio.
- Selective → four checkboxes (diagnostics labels, English in UI matching
  existing tone).
- Bulk Apply Proxy may set pool id and optionally push current usage
  template from the chosen pool (same as single assign defaults).

### `/proxy-pools`

- Edit form: default usage mode + Selective flags.
- Button: **Apply usage settings to all connections using this pool**
  → updates each matching connection's `data.proxyUsage` (does not clear
  `proxy_pool_id`).

## Runtime

### Purpose enum

| Purpose | Call sites |
|---------|------------|
| `testConnection` | Single/bulk connection test, validate helpers used by test |
| `testModel` | `/models/test` |
| `testChat` | Chat playground requests tagged with purpose header |
| `oauthRefresh` | Token refresh / OAuth token HTTP |
| `upstream` | Default for `/v1/*` and other production forwards |

### Header

Chat UI (and any diagnostic client that must stay Selective-safe) sends:

`X-9Router-Purpose: test-chat`

Mapped to purpose `testChat`. Unknown/missing → `upstream`.

### Resolution

```
need_proxy = mode == "all"
  or (mode == "selective" and flags[purpose] and purpose != "upstream")
if not need_proxy: return None  # direct
load ProxyPool by conn.proxy_pool_id
if missing or inactive:
  if pool.strict_proxy: fail request
  else: return None
return pool.proxy_url
# optional v1: honor no_proxy host list
```

All upstream `httpx` sites that represent connection-bound traffic should
use the factory (or receive an explicit `proxy=` from the resolver).  
Provider `validate()` paths used by connection test must accept optional
proxy URL (thread through `_test_provider_connection`).

## Success criteria

1. Mode **off** → no proxy on test or `/v1/*`.
2. Mode **selective** + `testConnection` → bulk/single test uses pool;
   Cursor `/v1/chat/completions` does not.
3. Mode **selective** + `testChat` → Chat page uses pool; external clients
   do not (unless they spoof the header — accept for v1; document).
4. Mode **all** → test and `/v1/*` use pool.
5. Pool mass-apply updates `proxyUsage` on all connections bound to that
   pool.
6. Inactive/missing pool: direct unless `strict_proxy`.

## Follow-ups

- Harden purpose header (signed or internal-only path) if spoofing matters.
- `no_proxy` matching beyond simple host list.
- Settings `outboundProxy` as fallback when connection has no pool.
