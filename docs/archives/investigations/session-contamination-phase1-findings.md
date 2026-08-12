# Session Contamination — Phase 1 Findings

**Date:** 2026-08-10  
**Status:** Phase 1 complete — final verdict recorded (operator confirmed)  
**Incident session:** `session_bf3127d4-82e6-47f4-942f-61db3a64ec0f`  
**Wire:** `/home/bejo6/.kimi-code/sessions/wd_9router-fastapi_ee0e704dba20/session_bf3127d4-82e6-47f4-942f-61db3a64ec0f/agents/main/wire.jsonl`  
**Plan:** `docs/investigations/session-contamination-reinvestigation-plan.md`  
**Prior report (flawed root cause):** `docs/investigations/session-contamination-investigation.md`

---

## Phase 0

**Incident statement:** At 2026-08-10 ~20:15:34 +07, Kimi session
`session_bf3127d4-82e6-47f4-942f-61db3a64ec0f` (workspace 9router-fastapi)
received content that describes / targets `grok-farm-modular` and matches
the parallel omp chat topic.

**Contamination status:** CONFIRMED.

**Kimi `base_url` (current config.toml):**
`fastapi-9router` → `http://localhost:5173/v1`  
(omp path at incident time still unknown — A3 open)

---

## Phase 1.1 — Fingerprint (Kimi side)

Contaminated payload (wire line 2520 `turn.prompt` / 2521
`context.append_message`) exact text:

```
ko jadi balik lagi error
```
 /mnt/E07854D07854A6D6/Project/external-repo/grok-farm-modular

───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


 gw mau nambah provider baru , nanti tugas lu cuma buat flow yang rapih ...
 - __dev/provider-alibaba-cloud.md
 - __dev/provider-mistral.ai.md
 - __dev/provider-qoder.md
 ...
 Error: OpenAI responses stream closed before a terminal response event was received
 (×4)
```
```

Also stored verbatim in Kimi user-history:

`/home/bejo6/.kimi-code/user-history/edf6a1ab15bf76aad6e2843ac70a20a4.jsonl` line 218

History order around it:

| Hist # | Content head |
|--------|----------------|
| 216 | `!pwd` |
| 217 | `/compact` |
| 218 | contaminated block (exact) |
| 219 | `kenapa jadi scan projek lain...` |

**Match class vs omp transcript:** `near` / topic-confirmed by operator
(A2 exact export still optional). Crossed: task text, `__dev` files, path,
stream-closed errors. **Not crossed into this user turn:** omp Glob UI
chrome, dashboard `:3847`, full omp assistant reply.

---

## Phase 1.2 — Wire event shape

| Line | Event | Note |
|------|-------|------|
| 2503 | `full_compaction.begin` | `source: manual` |
| 2509 | `full_compaction.cancel` | cancelled; not proof of bad stream |
| 2510–2511 | shell `pwd` → stdout `.../9router-fastapi` | `origin.kind: shell_command` |
| 2512 | `full_compaction.begin` | retry, `source: manual` |
| 2516 | `context.apply_compaction` | summary is **correct 9router-fastapi** handoff (rerank work, etc.) |
| 2519 | `full_compaction.complete` | 20:04:34 +07 |
| 2520 | `turn.prompt` | **`origin.kind: user`** — 20:15:34 +07 |
| 2521 | `context.append_message` role=user | same text; `origin.kind: user` |
| 2523+ | `llm.request` loop | model `fastapi-9router/qd/qoder/kmodel_latest` |
| 2527+ | tools on `grok-farm-modular` | hijack cascade |
| 2590 | `turn.cancel` | `reason: user_cancelled` (~29s later) |
| 2595 | user: out of scope / 9router | operator correction |

**Gap:** compaction complete → contaminated prompt ≈ **660 seconds
(~11 minutes)**. Foreign text is **not** inside the compaction summary.

**How Kimi stored it:** as a normal **user-origin prompt**, then sent that
text to the LLM. This is request-side contamination from Kimi’s point of
view, not a post-hoc mis-parse of an assistant SSE blob into a user turn
during compaction.

---

## Phase 1.3 — Backend logs

**Status:** `logs_unavailable` (not checked / not retained for that
window in this pass).

Not required to overturn the DeepSeek “Vite SSE mix during compaction”
story: compaction already finished cleanly **before** the foreign prompt.

---

## Phase 1.4 — Gate + final verdict

| Cheat-sheet row | Applies? |
|-----------------|----------|
| Kimi **request/prompt** already contains omp-shaped text | **YES** (wire 2520/2521 + user-history 218) |
| Kimi request clean; response mixed | No evidence in this window |
| Vite SSE mix during compaction | **Falsified for this incident timeline** |

### Operator confirmation (2026-08-10)

- `!<command>` entries (e.g. `!pwd`) and `/compact` are **intentional**
  Kimi features / human actions — not part of any paste.
- Contaminated block (history 218 / wire 2520): operator **intentionally
  pasted** omp chat + logs into the Kimi 9router session to work on
  fixing `OpenAI responses stream closed before a terminal response
  event was received` (omp → 9router path). The paste also contained the
  earlier “nambah provider” task text. Operator did **not** clearly
  restate the intended fix scope, so Kimi treated the pasted provider
  task as the active request and continued that work in
  `grok-farm-modular`.

### Verdict

**Operator paste with ambiguous intent** (not a 9router/Vite stream-mix bug)

Foreign `grok-farm-modular` / omp-shaped content entered the Kimi session
as a normal user prompt after a successful `/compact`. Kimi correctly
(from its point of view) followed the most salient task text inside the
paste (“nambah provider…”), instead of the stream-error fix the operator
meant to discuss.

| Layer | For this incident |
|-------|-------------------|
| `vite_proxy` | Not implicated |
| `fastapi_backend` | Not implicated |
| `client_kimi` / paste | **Implicated** |
| `client_omp` | Source of pasted text only |

**Rejected claim from prior investigation:** “Root cause = Vite proxy SSE
stream mixing” — inconsistent with clean compaction, 11-minute gap,
`origin.kind: user`, user-history prompt record, and operator paste
confirmation.

**Engineering action on 9router:** none required for this incident.
Optional hygiene: keep agent CLIs focused; avoid pasting other-terminal
dumps into an active Kimi session.

Phase 2 reenactment: **not needed** for this case.

---

## Timeline (local +07)

```
10:22  turn 23 ended
14:45  compact begin (manual)
14:54  compact cancel
15:15  !pwd → 9router-fastapi
20:01  compact begin (manual)
20:04  compact complete (summary = 9router, clean)
20:15  USER prompt with grok-farm / omp-shaped paste  ← contamination
20:15–20:16  agent reads/greps grok-farm-modular
20:16  user cancel + “out of scope”
```
