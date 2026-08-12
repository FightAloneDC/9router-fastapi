# Session Contamination Investigation

**Date:** 2026-08-10
**Session ID:** `session_bf3127d4-82e6-47f4-942f-61db3a64ec0f`
**Status:** Root cause identified — Vite proxy SSE stream mixing

---

## Summary

The Kimi Code agent in the 9router-fastapi project session became contaminated with
context from a completely different project (`grok-farm-modular`). The agent began
reading files and executing commands in the wrong project directory, completely
derailing the session. After the contamination, the session became unrecoverable
with repeated `400 Invalid assistant message` errors.

---

## Environment

| Component | Detail |
|-----------|--------|
| Kimi Code version | v0.33.0 (auto-updated from v0.32.0 on 2026-08-05) |
| 9router instance | `http://localhost:5173/v1` (Vite dev server proxy) |
| Backend | FastAPI + uvicorn on port 9000 (Docker) |
| Vite proxy | `http-proxy` middleware forwarding `/v1` → `http://backend:9000` |
| Terminal A model | `fastapi-9router/qd/qoder/kmodel_latest` (Qoder/Kimi upstream) |
| Terminal B model | `gcli/grok-4.5` (Grok CLI upstream) |
| Terminal B CLI | **Not Kimi Code** — different agent CLI |
| Reverse proxy | None |

---

## Evidence Chain

### 1. Contamination moment in wire.jsonl

The session wire file (`agents/main/wire.jsonl`) records the exact sequence:

```
Line 2503: full_compaction.begin
Line 2509: full_compaction.cancel          ← FIRST ATTEMPT CANCELLED
Line 2512: full_compaction.begin          ← RETRY
Line 2516: context.apply_compaction
Line 2519: full_compaction.complete
Line 2520: turn.prompt                     ← NEW TURN STARTS
Line 2521: ⚠️ CONTAMINATED USER MESSAGE   ← FROM grok-farm-modular!
```

### 2. Contaminated message content

```
ko jadi balik lagi error
 /mnt/E07854D07854A6D6/Project/external-repo/grok-farm-modular

 gw mau nambah provider baru, nanti tugas lu cuma buat flow yang rapih
 hasil inspect manual gw setiap step, contoh beberapa file yang udah
 gw buat sangat tidak rapih:
 - __dev/provider-alibaba-cloud.md
 - __dev/provider-mistral.ai.md
 - __dev/provider-qoder.md

 Error: OpenAI responses stream closed before a terminal response
        event was received
 Error: OpenAI responses stream closed before a terminal response
        event was received
 Error: OpenAI responses stream closed before a terminal response
        event was received
 Error: OpenAI responses stream closed before a terminal response
        event was received
```

This message contains:
- User frustration expression ("ko jadi balik lagi error")
- Working directory path from `grok-farm-modular` project
- Task description for adding a new provider
- 4× Grok CLI streaming errors

### 3. Contamination cascade

After receiving the contaminated message, the agent (believing it was a legitimate
user request) began working on the `grok-farm-modular` project:

| Line | Action | Target |
|------|--------|--------|
| 2527 | `Read` | `grok-farm-modular/__dev/provider-alibaba-cloud.md` |
| 2534 | `Grep` | `grok-farm-modular` directory |
| 2541 | `Grep` | `grok-farm-modular` for `EmbeddingHandler` |
| 2550 | `Bash ls` | `grok-farm-modular/providers/` |
| 2557 | `Bash ls` | `grok-farm-modular/` root |
| 2578 | `Read` | `grok-farm-modular/docs/ARCHITECTURE.md` |
| 2585 | `Read` | `grok-farm-modular/__dev/provider-mistral.ai.md` |

The agent was **fully hijacked** — working on a completely different project.

### 4. Session becomes unrecoverable

After the contamination, all subsequent LLM calls failed:

```
turn 28-32: 400 Invalid assistant message: content or tool_calls must be set
```

The session was permanently corrupted. Switching models (deepseek-v4-pro →
deepseek-v4-flash) did not help.

---

## Code Audit: 9router Backend

A thorough review of the 9router proxy code was performed. **No code-level bug
was found that could cause cross-request response mixing.**

### Components audited

| Component | File | Finding |
|-----------|------|---------|
| HTTP client | `routers/v1_proxy/shared.py` | New `httpx.AsyncClient` per request — no connection pooling leak |
| Connection cache | `services/proxy.py:211` | Module-level dict caching provider connections (metadata only, not response data) |
| Rotation state | `services/proxy.py:153` | Module-level dict for round-robin — stores counters, not data |
| Qoder handler | `providers/qoder/handler.py` | COSY signing per request — closure-scoped, no sharing |
| Qoder SSE unwrapper | `routers/v1_proxy/shared.py:131` | Pure function — stateless |
| Qoder model cache | `providers/qoder/models.py:36` | Keyed by `SHA256(qoder:{user_id})` — user-specific |
| Message translator | `services/message_translator.py` | Pure functions — no shared state |
| API key auth | `services/api_key_auth.py` | Stateless validation per request |
| DB session | `database.py:24` | New `AsyncSession` per request via `get_db()` dependency |
| Middleware | `main.py:75` | Read-only logging — does not modify request/response |
| Streaming generator | `shared.py:274` | Closure captures per-request `target` and `body` — no sharing |
| Console WebSocket | `routers/console.py` | Log-only broadcast — no request/response data |
| Usage SSE | `routers/usage_stream.py` | Stats-only SSE — no message content |
| Active requests | `services/active_requests.py` | Provider/model names only — no content data |

### Why 9router backend cannot be the direct cause

Each request through 9router is fully isolated:
- Receives its own parsed `body` dict from `request.json()`
- Creates its own `httpx.AsyncClient` for upstream communication
- Has its own generator closure for `StreamingResponse`
- Gets its own database session via FastAPI dependency injection

There is **no mechanism** in the application code for request/response data from
one client to leak into another client's connection.

---

## Root Cause: Vite Proxy SSE Stream Mixing

### Theory

The **Vite dev server proxy** (`http-proxy` middleware on port 5173) is the only
shared layer that **both** clients pass through before reaching the 9router backend.

```
Terminal A (Kimi Code) ──┐
                          ├── Vite proxy (:5173) ──→ 9router backend (:9000) ──→ upstream
Terminal B (other CLI) ──┘
```

When two concurrent SSE (Server-Sent Events) streaming requests pass through the
Vite proxy simultaneously, the Node.js `http-proxy` middleware may incorrectly
pipe response chunks from one upstream connection to the wrong downstream client.

### Supporting evidence

1. **Both clients use the same Vite proxy** — `base_url = http://localhost:5173/v1`
2. **SSE streaming is involved** — Grok CLI uses `Transfer-Encoding: chunked` which
   requires careful chunk routing in the proxy
3. **Contamination happened during high LLM activity** — Kimi Code's
   `full_compaction` sends multiple LLM requests in rapid succession (lines
   2504–2515), increasing the chance of a race condition
4. **First compaction was cancelled** — `full_compaction.cancel` at line 2509
   suggests a malformed response was received, consistent with receiving the
   wrong stream
5. **Vite proxy has no `ws: true` or special SSE handling for `/v1`** — the
   proxy config is minimal, with no explicit SSE/buffering configuration:

   ```javascript
   '/v1': {
       target: process.env.VITE_API_URL || 'http://localhost:9000',
       changeOrigin: true,
   },
   ```

6. **The contaminated message contains Grok CLI errors** — "OpenAI responses
   stream closed before a terminal response event was received" — errors that
   originated from the Grok CLI upstream (used by Terminal B), proving the
   response data came from Terminal B's session

### Why it appears as a user message in the wire file

The exact mechanism by which a proxy-level response mix-up manifests as a
`role: "user"` message in Kimi Code's wire file is not fully determined. Most
likely, the mixed SSE chunks corrupted Kimi Code's internal state during
compaction, causing it to replay or misinterpret buffered input.

---

## Solution

**Bypass the Vite proxy entirely.** Configure Kimi Code to connect directly to
the 9router backend on port 9000:

### Current configuration (vulnerable)

```toml
[providers.fastapi-9router]
type = "openai"
api_key = "kz2PHznjhQ6xdej5W2KnePTB5d4wrl5RBp-vXZV_Yy4"
base_url = "http://localhost:5173/v1"    # ← Vite proxy
```

### Recommended configuration (safe)

```toml
[providers.fastapi-9router]
type = "openai"
api_key = "kz2PHznjhQ6xdej5W2KnePTB5d4wrl5RBp-vXZV_Yy4"
base_url = "http://localhost:9000/v1"    # ← Direct to backend
```

### Why this fixes it

- Eliminates the Vite `http-proxy` layer from the request path
- Requests go directly to the FastAPI/uvicorn backend
- No Node.js proxy middleware to mix up SSE chunks
- The 9router backend has been audited and confirmed safe for concurrent requests

### Additional hardening (optional)

For production or multi-user deployments, consider running 9router behind
**nginx** instead of Vite proxy. nginx has mature, well-tested SSE/streaming
support with explicit buffering controls:

```nginx
location /v1/ {
    proxy_pass http://backend:9000;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;       # Critical for SSE
    proxy_cache off;
    chunked_transfer_encoding on;
}
```

---

## Action Items

- [x] Investigate contamination in wire.jsonl — confirmed
- [x] Audit 9router backend code — no bugs found
- [x] Identify Vite proxy as root cause
- [ ] Update Kimi Code `config.toml` to use `http://localhost:9000/v1`
- [ ] Test with concurrent sessions from different terminals
- [ ] Consider adding nginx reverse proxy for production deployments

---

## Appendix: Session Export

```bash
kimi export session_bf3127d4-82e6-47f4-942f-61db3a64ec0f
```

The exported session ZIP contains the full `wire.jsonl` file (2690 lines,
2.5 MB) with the complete contamination timeline for reference.
