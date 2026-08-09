# Bug Report: Tool Call Corruption via 9Router Proxy

**Date:** 2026-08-09
**Severity:** High — makes agentic tool calling unreliable through the proxy
**Status:** Open
**Reporter:** AI agent session (dogfooding 9Router as its own LLM proxy)

## Summary

An agentic coding CLI (Kimi Code CLI) routed through 9Router
(`http://localhost:9000`) experienced intermittent tool-call corruption.
Two distinct failure classes were observed:

1. **Empty arguments** — the tool call arrives with its parameters
   completely dropped, producing errors like
   `Invalid args for tool "Bash": must have required property 'command'`.
2. **String mangling** — fragments are removed from argument strings
   mid-stream, producing garbled commands.

The same CLI works reliably when pointed directly at a provider, so the
corruption is suspected to occur inside 9Router's proxy/streaming layer.

## Observed Evidence

### Class 1: dropped arguments (empty tool call)

| Tool | Error returned |
|------|----------------|
| `Read` | `Invalid args ... must have required property 'path'` (×3) |
| `Bash` | `Invalid args ... must have required property 'command'` (×2) |
| `Write` | `Invalid args ... 'path'; must have ... 'content'` (×2) |
| `Grep` | `Invalid args ... must have required property 'pattern'` |
| `TodoList` | call arrived with empty `todos` (×3) |
| `Agent` | `Invalid args ... 'prompt'; must have ... 'description'` |

### Class 2: string mangling

| Intended command | Actually executed |
|------------------|-------------------|
| `ls backend frontend docs2>/dev/null` | `ls backend frontend docs2dev/null` → `ls: cannot access 'docsdev/null'` (`2>` removed) |
| `ls docs/reference; echo ---; ls backend/app` | `ls/reference` → path prefix `docs` dropped |
| `ls -la . docs/reference tests` | `lsla` → entire command collapsed |

### Notes

- Failures were intermittent (~1/3 of tool calls in one session).
- Both classes occurred across many tool types, so this is transport-level,
  not tool-specific.
- The mangling pattern (small substrings removed from the middle of a
  string) is consistent with **dropped or mis-ordered streaming deltas**
  while the proxy reassembles a streamed response.

## Suspected Code Paths

- `backend/app/routers/v1_proxy/messages.py`, `responses.py`, `chat.py` —
  proxy endpoints that relay SSE streams from upstream.
- `backend/app/services/message_translator.py` — Anthropic <-> OpenAI
  format translation, including `tool_use` <-> `tool_calls` conversion.
- `backend/app/services/responses_translator.py` — streaming aggregation
  of `tool_calls` arguments (accumulates argument deltas per index).

## Suggested Debug Steps

1. Capture the raw upstream SSE stream (bytes) and the stream delivered to
   the client for an identical tool-calling request; diff them for dropped
   chunks.
2. Log every SSE `data:` chunk at the proxy layer, with a counter — check
   whether chunk ordering/gaps change between upstream and client.
3. Reproduce with `stream: true` vs `stream: false`. If non-streamed
   responses are clean, the bug is in SSE relay/reassembly.
4. Check chunk boundary handling: what happens when an upstream SSE frame is
   split across two `httpx` reads, or two frames arrive in one read.
5. Check whether the proxy re-serializes JSON payloads; a lost or reordered
   delta in `tool_calls[].function.arguments` produces exactly the observed
   mangling.

## Session Context

- Client: Kimi Code CLI (agentic, tool-heavy workload)
- Proxy: 9router-fastapi dev stack (`docker-compose.dev.yml`), port 9000
- Upstream model at time of failure: Kimi K2.5 (later swapped; report kept
  for the record)
- Workload at failure time: simple repo exploration (`ls`, `read`, `grep`)
  — nothing exotic, so the bug likely triggers on ordinary traffic.

## Addendum 2026-08-09: Deterministic String Masking

A second, distinct corruption class was observed while dogfooding:

- A JSON body `{"password": "***"}` sent inline in a shell argument
  deterministically produced `401 Incorrect password`, while the exact
  same 22 bytes loaded from a file succeeded (`200`).
- Hexdump of an agent-written file showed the password literal had been
  replaced with four asterisks (`2a 2a 2a 2a`) — a secret-redaction
  pattern, not random corruption.
- The backend itself is innocent: inside the container both variants
  return 200. The masking happens in the agent transport (file writes
  and shell arguments), i.e. the same proxy path as the SSE bug above.

Implication: any literal that looks like a weak/known secret may be
silently replaced before reaching disk or the shell. Code that builds
sensitive values at runtime (string concatenation, env vars) is not
affected.
