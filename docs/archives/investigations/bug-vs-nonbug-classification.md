# Bug vs Non-Bug Classification

**Date:** 2026-08-11  
**Status:** Living notes — **errata 2026-08-11 05:59** (goal `/goal` re-audit)  
**Scope:** Symptoms seen in Codex, omp (π), Kimi while routing through 9router  
**Related:**
- `session-contamination-phase1-findings.md`
- Stream / Responses fixes in `backend/app/routers/v1_proxy/responses.py`,
  `backend/app/services/responses_translator.py`,
  `backend/app/providers/grok_cli/stream.py`

Use this when a turn looks “putus”, “nyangkut”, or “salah project”. Classify
**before** changing 9router code.

---

## Errata (2026-08-11) — prior “Phase 9 = not a bug” was too narrow

Earlier triage labeled announce-then-stop (Phase 9 text) as **B2 = not a
9router bug**. That was **wrong as a product verdict**.

What was true:
- That single turn had `stopReason: stop`, no `stream closed` string, SSE
  finished with a normal stop — so it was **not classic A1**.

What was missing:
- In the same crypto omp session under `/goal` + `qd/qmodel`, the same
  pattern repeats: assistant ends with **text only** (“Saya akan… sekarang”)
  and **no `toolCall`**, so the agent loop stalls until a user/goal
  continuation kick. User experience = **putus-putus**.
- Session stats (crypto `019fed79…`): after Phase 9,
  `toolCall` turns ≈ 267 vs `stop` without tool ≈ 18 — intermittent but
  real.
- omp log during goal: many
  `hasToolCalls: false` + `stopReason: stop` while `goalModeEnabled: true`.
- Title-generator once got tool syntax as **text**
  (`<call>list_files{path: "frontend"}<call>`) — tool protocol leak / not
  executed as a tool.

**Corrected label:** treat recurring mid-task `stop` without tool during
`/goal` as **open defect class G1** (agent stall). Root cause may be model,
omp goal loop, **or** proxy tool-stream translation — **not yet proven
inside 9router**, but **must not be dismissed** as “not a bug”.

---

## Quick rule

| Signal | Likely |
|--------|--------|
| Client error: `OpenAI responses stream closed before a terminal response event was received` | **Bug (or was)** — missing terminal SSE (**A1**) |
| Mid-task “I will write/fix X now” then idle; `stop` + no tool; repeats under `/goal` | **Real stall (G1)** — open; do not close as “not a bug” |
| Foreign project text appears as a **user** turn after you pasted logs | **Not a 9router bug** — paste / ambiguous brief (**B1**) |
| HTTP 429 / empty content with `finish_reason: length` on reasoning models | **Not a 9router bug** — upstream / token budget (**B4/B5**) |
| One-off 0-byte hang that succeeds on retry | **Flaky upstream / load (B6)** until reproducible |
| User abort / Interrupted by user | **Not a proxy bug (B3)** |

---

## A. Confirmed / fixed 9router bugs

These are real proxy defects (or were, and got fixes). Re-open if they return
after the fixes below.

### A1. Missing terminal Responses events → client “stream closed”

**Symptom (client):**  
`OpenAI responses stream closed before a terminal response event was received`

**What it means:** HTTP SSE ended without a terminal event
(`response.completed` / `response.failed` / `response.incomplete`, or chat
`finish_reason` + `[DONE]` on translated paths).

**Root causes found:**
1. Chat→Responses translator did not finalize when upstream ended without
   `finish_reason`.
2. Grok Responses→Chat translator did not emit terminal chat SSE on early
   close.
3. Grok / Responses passthrough could miss terminal detection when events
   were split across TCP chunks (needed SSE line buffering).

**Fix areas:** `ResponsesStreamTranslator.finalize()`,
`ResponsesUpstreamTranslator.close()`, passthrough SSE line buffer,
incomplete terminal SSE helpers.

**How to classify a new case:** Look at the raw SSE from 9router. If the
stream ends with no terminal event → **bug**. If terminal event is present
and the client still complains → client / SDK issue, not missing terminal.

### A2. `/v1/responses` hang (0 bytes) for some providers (e.g. Qoder)

**Symptom:** Chat completions OK; `/v1/responses` hangs ~tens of seconds with
**0 download bytes**.

**Root cause:** Responses path skipped provider request build / SSE unwrap
that chat already had (e.g. Qoder COSY).

**Fix:** Align responses path with chat (`_build_provider_request` + unwrap).

### A3. Tool calls stop after text / empty `response.completed.output`

**Symptom:** Agent hangs after assistant text when tools are required;
stream has `output_item.done` but `response.completed.output` is `[]`.

**Root cause:** Translator streamed incomplete tool-call event sequence /
did not fill `completed.output` with `function_call` items.

**Fix:** Emit `output_item.added`, `function_call_arguments.delta/done`, and
populate `completed.output`.

### A4. Dual terminal (`response.completed` + `response.incomplete`)

**Symptom:** Battery / client sees both completed and incomplete on one
stream.

**Root cause:** Chunk-split miss on terminal detection in passthrough;
finalize also firing.

**Fix:** SSE line buffer before terminal detection; avoid double finalize
once a terminal was already sent.

---

## B. Not 9router bugs (do not “fix” in proxy)

### B1. Session “contamination” (Kimi got grok-farm / omp text)

**Verdict:** Operator paste + ambiguous brief.  
**Evidence:** Contaminated block entered as `turn.prompt` /
`origin.kind: user`, ~11 minutes after clean compaction — not SSE mixing.  
**Doc:** `session-contamination-phase1-findings.md`.

**Not:** Vite proxy mixing response streams into another session’s user
message.

### B2. (SUPERSEDED) single announce-stop ≠ proof of A1

A lone turn with `stopReason: stop` and no `stream closed` string is
**not A1**. That observation remains valid.

It is **not** permission to close the ticket. See **G1** below — the same
symptom class is a recurring `/goal` stall and stays **open**.

### B3. User abort

**Example:** omp `stopReason: aborted`, `errorMessage: Interrupted by user`
on `gcli/grok-4.5`.

**Verdict:** Not a proxy bug.

### B4. Upstream rate limit (429)

**Example:** `mi/mistral-large-latest` responses cases failed with Mistral
`429 Too Many Requests` during burst battery.

**Verdict:** Upstream quota / rate limit. Proxy correctly surfaced error
(sometimes plus finalize empty completed — see note below).

### B5. Reasoning models + tiny `max_tokens` → empty visible answer

**Example:** `bb/z-ai/glm-5.2` chat text with `max_tokens: 32`:
`finish_reason: length`, only `reasoning_content`, no `delta.content` /
PONG.

**Verdict:** Model burned the budget on reasoning. Not a cut stream
(`[DONE]` was present).

### B6. Flaky upstream hang that retries clean

**Example:** `bb/blackboxai/z-ai/glm-5.2-vercel` `/v1/responses` + tools
timed out 120s / 0 bytes twice; immediate retry completed with
`function_call` in ~1.2s.

**Verdict:** Treat as flaky upstream / load until reproducible with
backend evidence. Do not equate to A2 without proof the hang is inside
9router (no provider build, no unwrap, etc.).

---

## G. Open defects (real UX failure; root layer TBD)

### G1. Mid-task agent stall — `stop` without tool (`/goal` putus-putus)

**Symptom (user):** Agent bilang akan lanjut / write / fix, lalu berhenti;
`/goal` terasa putus-putus; kadang lanjut lagi setelah kick user/continuation.

**Example text:**

```
Oke bro, lanjut ke Phase 9.
Saya akan buat file frontend/docs/phase-9-testing.md sekarang.
```

**Evidence (crypto session `019fed79…`, 2026-08-11):**
- Model `qd/qmodel` / provider `fastapi-router`
- Recurring: `stopReason: stop`, content `thinking`+`text`, **no** `toolCall`
- Not always A1: no `OpenAI responses stream closed…` on those turns
- After Phase 9 window: ~267 tool turns vs ~18 stop-without-tool
- omp: `hasToolCalls: false` while `goalModeEnabled: true`
- Aftermath: next event often a `user` (or goal continuation) then
  `toolUse` — loop resumes only after an extra kick
- Some early qd turns used `api: openai-responses` with `usage.output: 0`
  while text still present (recording / path quirk — investigate)
- Title-generator returned `<call>list_files{...}<call>` as title text
  (tool-shaped text, not executed)

**Verdict:** **Real bug for `/goal` UX (open).**  
**Not classified as fixed A1.** Possible layers (investigate in order):
1. Proxy drops / mistranslates `tool_calls` on Qoder chat or Responses path
2. Upstream model emits stop + prose instead of tool_calls intermittently
3. omp goal continuation too slow / does not auto-reprompt on announce-only

**Next proof needed (do not guess):**
- Capture one stall turn’s **raw SSE** from 9router (`finish_reason`,
  `tool_calls` / Responses function_call events).
- If terminal + empty tools in raw SSE → model/upstream (still product bug).
- If upstream had tools but client session has none → **9router bug**.
- If raw SSE incomplete / no terminal → **A1 regression**.

**Live catch (2026-08-11 06:01:13 +07) — same session, just stalled:**
- Session line 1170, `responseId=chatcmpl-db76a03e-cdda-9cf1-a040-a412ae9cc662`
- `api=openai-completions`, `stopReason=stop`, `errorMessage=null`
- `output=44` tokens, content types `thinking`+`text`, **no toolCall**
- Text: `**PERFECT! NO TYPESCRIPT ERRORS!** ✅` then `Sekarang rebuild Docker:`
- Prior turns were healthy `toolUse` (bash/read/write). Stall = announce next
  step without issuing the tool. omp log same second:
  `hasToolCalls: false`, `stopReason: stop`.
- **Not A1** on this turn (no stream-closed error). **Is G1.**

---

## C. Gray area (proxy behavior to watch, not the original “stream closed”)

### C1. Error event then empty `response.completed`

On some upstream failures (e.g. 429), clients may see `event: error` and
still get a finalized `response.completed` with empty `output`.

That can confuse analyzers (`comp=True` while the request failed). It is
**not** the same as A1 (missing terminal). Decide later whether empty
completed after error should be `response.failed` instead — separate
ticket from “stream closed”.

---

## D. Decision checklist (paste into triage)

1. **Capture:** model alias, endpoint (`/v1/chat/completions` vs
   `/v1/responses`), client (Codex / omp / Kimi), timestamp.
2. **Raw SSE / session:** Was there a terminal event? `stopReason`?
   `errorMessage`?
3. **Map:**
   - No terminal → **A1** (regression?)
   - Hang 0 bytes on responses only → **A2**?
   - Tools required, empty `completed.output` → **A3**?
   - Dual terminal → **A4**?
   - Announce-only / `stop` without tool → **B2**
   - Paste as user turn → **B1**
   - User interrupt → **B3**
   - 429 / length-only reasoning → **B4** / **B5**
4. **Only then** change 9router code.

---

## E. Battery notes (context, not pass/fail of “bug fixed”)

| Route | Result (Aug 10–11) | Notes |
|-------|--------------------|--------|
| `gcli/grok-4.5` | Mostly pass after terminal fixes | One flaky tool case (model/`tool_choice`) |
| `mi/codestral-latest`, `mi/mistral-code-agent-latest` | 8/8 | |
| `mi/mistral-large-latest` | 5/8 | Failures = **B4** 429 |
| `bb/z-ai/glm-5.2` | Chat text “fail” = **B5** | Responses/tools OK |
| `bb/.../glm-5.2-vercel` | Tool hang then OK on retry = **B6** | |

---

## F. One-liners for chat

- **“Stream closed before terminal event”** → treat as **proxy bug** until
  proven otherwise (A1).
- **“Oke bro… saya akan buat file sekarang” then idle / putus di `/goal`**
  → **real stall (G1)**; not “bukan bug”. Check raw SSE before blaming
  only the model or only 9router.
- **Wrong project / foreign paste in session** → **not** Vite mix; paste
  (B1).
