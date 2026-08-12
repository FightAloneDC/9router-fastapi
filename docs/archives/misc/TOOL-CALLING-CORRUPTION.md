# Bug Report: Tool Call Corruption via 9Router Proxy

**Date:** 2026-08-09
**Severity:** High — makes agentic tool calling unreliable through the proxy
**Status:** Resolved (root cause found + fixed 2026-08-09)
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

## Resolution 2026-08-09: Root Cause Found and Fixed

### Root cause

`_stream_response()` in `backend/app/routers/v1_proxy/shared.py`,
Qoder branch. Qoder wraps each OpenAI chunk in an SSE envelope
(`{"statusCodeValue":200,"body":"..."}`). The relay decoded each
httpx read independently and split it on newlines **without carrying
partial lines over to the next read**:

```python
async for chunk in resp.aiter_bytes():
    text = chunk.decode("utf-8", errors="ignore")
    for line in text.split("\n"):          # fragments dropped
        unwrapped = _unwrap_qoder_sse_line(line)
```

A `data:` line split across two TCP reads was processed as two
invalid fragments; `_unwrap_qoder_sse_line()` returned `None` for
both and they were silently dropped. Consequences:

- A dropped `tool_calls[].function.arguments` delta truncated or
  emptied the arguments -> `Invalid args ... must have required
  property 'command'` (Class 1).
- A dropped `content` delta removed substrings from text and command
  strings (Class 2).
- Multi-byte UTF-8 chars split across reads were eaten by
  `errors="ignore"`.

Read boundaries are arbitrary, so failures were intermittent and grew
with payload size — exactly the observed ~1/3 failure rate on long
agent contexts.

### Why only this path

- All Kimi Code CLI traffic used the Qoder connection
  (`qd/qoder/kmodel_latest` in `request_details`), so every agent
  turn went through this branch.
- Other providers use raw byte passthrough in the same function —
  split frames reach the client intact and are reassembled there.
- The Claude/Responses/Grok/Messages translation paths already buffer
  lines across reads (`while b"\n" in buffer: ...`) and were safe.

### Fix

Byte-level line buffer with carry-over in the Qoder branch (the same
pattern the other paths already use), plus a final-line flush for
payloads without a trailing newline. Usage capture moved into a
`_capture_qoder_usage()` helper. No behavior change for non-Qoder
providers — the change is fully contained in the `is_qoder` branch.

### Verification

- `backend/tests/test_qoder_stream.py` — a fake upstream writes the
  wrapped SSE in small delayed pieces so lines split across reads:
  tool-call arguments and multi-byte text reassemble intact; a final
  line without trailing newline is flushed. All 5 tests pass.
- The old logic, replayed against the same splitting server, parsed 0
  complete lines and reassembled the tool arguments as an empty
  string — reproducing Class 1 exactly.
- Live: streaming `/v1/chat/completions` through a real Qoder
  connection (`stream: true`, one `Bash` tool) returned 42 chunks,
  `finish_reason: tool_calls`, and the full valid arguments JSON.
- Full pytest suite: no new failures (7 pre-existing failures
  unrelated to this change, verified against the base code).

## Related Findings (not fixed here)

1. **Double upstream request** — `_stream_response()` fires a full
   pre-flight POST (which consumes the entire completion) before the
   real request for every non-Qoder streaming call. This doubles
   upstream quota usage per request. The pre-flight exists so HTTP
   errors can trigger connection fallback before streaming starts;
   the streaming translation paths skip it entirely.
2. **Responses-API tool-call indices** —
   `ResponsesStreamTranslator._flush_finish()` emits every tool
   call's `output_item.done` with the same `output_index`, emits no
   `output_item.added`/argument-delta events for tool calls, and
   sends `response.completed` with an empty `output` array. Parallel
   tool calls through `/v1/responses` can collide or be lost. Not on
   the path that failed here, but the same bug family.
