# Plan: Session Contamination Re-Investigation

**Date:** 2026-08-10  
**Status:** Active plan  
**Project:** 9Router FastAPI  
**Related:** `docs/investigations/session-contamination-investigation.md`  
**Incident session:** `session_bf3127d4-82e6-47f4-942f-61db3a64ec0f`

---

## Goal

Determine **which layer** leaked parallel-session content from the
`grok-farm-modular` / omp agent chat into the Kimi Code session on
9router-fastapi — without treating contamination itself as unproven.

**Contamination is already established by data.** This plan does **not**
require re-enacting the incident to “prove it happened again.”

Success = a written verdict with evidence that names one of:

| Verdict | Meaning |
|---------|---------|
| `vite_proxy` | Leak at Vite `http-proxy` (`:5173`) |
| `fastapi_backend` | Leak at 9router FastAPI / streaming path (`:9000`) |
| `client_kimi` | Leak / mis-persist inside Kimi Code |
| `client_omp` | Leak / mis-send inside omp / Grok CLI |
| `shared_client_config` | Wrong base URL, shared buffer, or human/OS mix |
| `inconclusive` | Artifacts insufficient; only then consider controlled A/B |

---

## Why the existing investigation is janggal

Source: `docs/investigations/session-contamination-investigation.md`

### 1. Root cause declared while mechanism is admitted unknown

Header says: **“Root cause identified — Vite proxy SSE stream mixing.”**  
Later: the mechanism by which mixed SSE becomes a `role: "user"` wire
event is **“not fully determined.”**

You cannot claim root cause and “mechanism unknown” in the same document.

### 2. Solution contradicts the “backend is clean” narrative

The doc concludes 9router FastAPI has **no** cross-request mixing bug,
then’s primary fix is: point clients at `http://localhost:9000/v1`.

That is a valid **isolation experiment**, not a proven fix, and it does
not logically follow from “backend audited clean.” It only follows if
Vite is proven guilty — which was not proven.

### 3. Evidence of foreign content ≠ evidence of Vite mixing

Overlap with omp / `grok-farm-modular` (path, provider-task text, stream
errors) proves **cross-session contamination**. It does **not** prove
Node `http-proxy` spliced SSE chunks.

Correlation of content source ≠ identification of the leaking layer.

### 4. Wrong failure mode for the claimed bug class

Claimed bug: concurrent SSE **response** chunk mixing.  
Observed artifact: a coherent **user-message-shaped** turn (task text +
cwd + errors), then the agent acted on another repo.

Typical stream mix-ups produce garbled assistant/SSE events, not a clean
user turn that looks like another chat’s prompt. The causal jump is
unexplained.

### 5. Speculative use of `full_compaction.cancel`

Cancel at wire line ~2509 is treated as proof of a malformed / wrong
stream. Cancel can also be user interrupt, timeout, client abort, or
compaction policy. Treating it as Vite evidence is over-interpretation.

### 6. No reproduction / no layer falsification, but status is “identified”

Action items still list concurrent testing as unchecked, yet status is
root-cause identified. Investigation stopped at a convenient layer
(Vite) after a negative backend code read.

### 7. Negative code audit overstated as impossibility

“No mechanism in application code” is stronger than a static review can
support (races, proxy in front of the app, client parse bugs, logging
gaps). A clean audit is useful; it is not a closed proof that FastAPI
cannot be involved.

### 8. Framing drift (DeepSeek / Kimi / omp)

The incident involves Kimi Code + omp/Grok CLI through the 9router path.
DeepSeek appears mainly as a post-corruption model switch. Treating the
write-up as a settled “DeepSeek investigation of 9router” obscures what
was actually tested.

### Out of scope for this critique

API keys pasted in the old doc (ops hygiene) — not part of the technical
root-cause critique.

---

## Non-goals

- Do not re-simulate the full dual-agent chaos **only** to re-prove
  contamination.
- Do not change production routing / “fix” Vite bypass as the conclusion
  before a verdict.
- Do not patch FastAPI “just in case” without a layer verdict.
- Do not expand into unrelated provider/proxy refactors.

---

## Artifacts to gather (before any live dual-session work)

Prefer existing evidence first.

| ID | Artifact | Why |
|----|----------|-----|
| A1 | Kimi export / `wire.jsonl` for incident session | Exact contaminated event + surrounding compaction turns |
| A2 | omp / Grok CLI session log or transcript from same window | Exact source text for string match |
| A3 | Both clients’ provider config at the time (`base_url`, model ids) | Confirms shared path (`:5173` vs `:9000` vs direct upstream) |
| A4 | Backend/Docker logs around contamination timestamp | Whether FastAPI saw omp-shaped body on Kimi’s request |
| A5 | Vite access/error logs if available | Only useful if timestamps align; often thin |
| A6 | Clock sync note | Local machine times for A1–A4 alignment |

If A1+A2 exist, Phase 1 can finish without starting new agent sessions.

---

## Phase 0 — Lock the question

- [ ] **0.1** Write one sentence incident statement:

  > At time T, Kimi session S received content C that originated from omp
  > session O on project `grok-farm-modular`.

- [ ] **0.2** Record both `base_url` values used during the incident
  (Kimi and omp). If unknown, mark `unknown` — do not invent.

- [ ] **0.3** Explicitly mark contamination status: **CONFIRMED**.  
  Remaining work = **layer attribution** only.

**Verify:** Phase 0 checklist complete; no root-cause language yet.

---

## Phase 1 — Forensic match on existing data (no reenactment)

### 1.1 Exact string / fingerprint compare

- [ ] Extract contaminated user (or other) payload from `wire.jsonl`
  near the documented compaction boundary (~lines 2503–2521).
- [ ] Extract the closest omp transcript segment (user task text, errors,
  any overlapping lines).
- [ ] Classify match:

  | Class | Definition |
  |-------|------------|
  | `exact` | Same contiguous string (modulo whitespace) |
  | `near` | Same task + same errors, wording drift |
  | `theme_only` | Same project topic only |

- [ ] Note what did **not** cross (e.g. omp Glob UI chrome, dashboard
  `:3847`, full assistant reply). Absence of CLI-UI-only chrome in the
  Kimi wire favors “API/prompt path” over “screen/UI buffer dump.”

**Verify:** Written match class + list of crossed vs non-crossed fragments.

### 1.2 Wire event shape

- [ ] Record event type/role for the contaminated entry (user / assistant /
  tool / compaction / other).
- [ ] Record whether it appears **after** `full_compaction.complete` as a
  new `turn.prompt`.
- [ ] Check whether preceding compaction LLM responses look truncated,
  mixed JSON, or foreign SSE.

**Verify:** One paragraph: “how Kimi stored the foreign text,” not “why
Vite did it.”

### 1.3 Backend log correlation (strongest 9router test without reenactment)

If Docker/backend logs from the incident window still exist:

- [ ] Find Kimi-related `/v1/*` requests in the same minute as the wire
  contamination.
- [ ] Check whether any request body / logged prompt fragment for that
  connection already contains omp task text **before** the model reply.
- [ ] Check whether any response path logged omp-like assistant text on
  a connection attributed to Kimi.

Interpretation cheat-sheet:

| Observation | Points toward |
|-------------|----------------|
| Kimi **request body** already contains omp text | Client Kimi / shared input / wrong paste into Kimi — **not** response mixing in 9router |
| Kimi request clean; Kimi **response** contains omp stream | Shared proxy/backend response mix **or** upstream mix |
| No useful logs | Phase 1 inconclusive on layer; go Phase 2 |

**Verify:** Fill the cheat-sheet row that matches evidence, or
`logs_unavailable`.

### 1.4 Phase 1 verdict gate

- [ ] If request-body already contaminated → draft verdict leaning
  `client_kimi` / `shared_client_config`; **do not** blame Vite/FastAPI
  for response mixing.
- [ ] If only response-side foreign content with clean request → keep
  `vite_proxy` and `fastapi_backend` as open suspects; continue Phase 2.
- [ ] If artifacts missing → `inconclusive` on layer; Phase 2 optional
  isolation only.

**Verify:** Short “Phase 1 conclusion” section appended to this plan or
to a new findings note. Still no code “fix” required.

---

## Phase 2 — Controlled isolation (only if Phase 1 leaves proxy/backend open)

Purpose: falsify layers. **Not** to re-prove contamination exists.

### 2.1 Minimal matrix (stop early when falsified)

Run the **smallest** concurrent load that resembles the incident
(two streaming clients, different models/upstreams if possible):

| Trial | Client A path | Client B path | If contamination-like mix appears |
|-------|---------------|---------------|-----------------------------------|
| T1 | `:5173/v1` | `:5173/v1` | Shared Vite+backend path still possible |
| T2 | `:9000/v1` | `:9000/v1` | Vite alone insufficient; suspect FastAPI or clients |
| T3 | `:5173/v1` | `:9000/v1` | Path-specific / asymmetric clue |

Rules:

- [ ] Use **distinct** prompt markers per client
  (e.g. `MARKER_KIMI_AAA`, `MARKER_OMP_BBB`) so mix is unambiguous.
- [ ] Log `X-Request-Id` (add temporarily if missing) on backend for
  every `/v1` stream.
- [ ] Do **not** call trial success “root cause Vite” unless T1 shows mix
  and T2 does not, under the same client software.

**Verify:** Table of trials with pass/fail and captured request ids.

### 2.2 Optional instrumentation (temporary, remove after verdict)

Only if T1/T2 stay ambiguous:

- [ ] Backend: log hash of first user message + last 32 chars per stream
  request id (no full secrets in lasting docs).
- [ ] Confirm generator/`StreamingResponse` closure stays per-request
  under concurrency (code review + log proof, not vibes).

**Verify:** Instrumentation PR or local patch noted; cleaned up after.

---

## Phase 3 — Verdict and actions

### 3.1 Write verdict

- [ ] One of the verdict enum values from Goal.
- [ ] Evidence bullets (artifact ids A1–A6, trial ids T1–T3).
- [ ] Explicit rejection of overclaimed statements in the old doc where
  applicable.

### 3.2 Actions by verdict

| Verdict | Allowed follow-up |
|---------|-------------------|
| `vite_proxy` | Document SSE proxy hardening; optional nginx; client may use `:9000` as workaround |
| `fastapi_backend` | File bug + failing reproduction test around streaming isolation; fix with evidence |
| `client_kimi` / `client_omp` | Document client limitation; no 9router code change required |
| `shared_client_config` | Fix configs / operator guidance |
| `inconclusive` | Keep monitoring hooks; **do not** ship speculative “fixes” |

### 3.3 Update docs

- [ ] Add `session-contamination-findings.md` (or amend with a clearly
  dated addendum) stating: contamination confirmed; layer verdict; what
  the old doc got wrong.
- [ ] Leave the original investigation file in place as historical; do
  not silently rewrite it into looking correct.

**Verify:** Findings doc cites evidence; no API keys; English only.

---

## Decision rules (do not violate)

1. **Contamination confirmed ≠ layer identified.**
2. **Bypass Vite is an experiment or workaround, not a proof.**
3. **No root-cause language** until Phase 1 or Phase 2 gate is satisfied.
4. **Prefer existing artifacts** over reenactment.
5. **Reenactment only** to falsify remaining suspects after Phase 1.
6. **Code changes in 9router** only under `fastapi_backend` (or clearly
   scoped proxy-config docs under `vite_proxy`).

---

## Suggested working order (checklist summary)

- [x] Phase 0 — lock question + configs (Kimi path known; omp A3 open)
- [x] Phase 1.1 — string fingerprint (Kimi wire + user-history; A2 optional)
- [x] Phase 1.2 — wire shape
- [ ] Phase 1.3 — backend log correlation (`logs_unavailable` this pass)
- [x] Phase 1.4 — gate (request-side / user-origin; Vite-during-compaction falsified)
- [x] Phase 2 — skipped (not needed for this incident)
- [x] Phase 3 — verdict: intentional omp paste with unclear fix scope; Kimi followed “nambah provider” text; 9router stream-mix not implicated

See also: `docs/investigations/session-contamination-phase1-findings.md`  

---

## Known artifact locations

### A1 — Kimi incident session (found)

```
/home/bejo6/.kimi-code/sessions/wd_9router-fastapi_ee0e704dba20/session_bf3127d4-82e6-47f4-942f-61db3a64ec0f/
├── state.json
├── logs/
└── agents/main/wire.jsonl    # 2690 lines, ~2.5 MB — contamination near end
```

Workspace bucket: `wd_9router-fastapi_ee0e704dba20`  
Session id: `session_bf3127d4-82e6-47f4-942f-61db3a64ec0f`

Optional export (if needed elsewhere):

```bash
kimi export session_bf3127d4-82e6-47f4-942f-61db3a64ec0f
```

### Still needed from operator

1. Path or paste of omp transcript covering the same minute (A2)  
2. Whether omp used `http://localhost:5173/v1`, `:9000/v1`, or direct
   upstream (A3)  
3. Whether Docker/backend logs from that window still exist (A4)

Without A2, Phase 1.1 fingerprint compare is partial (Kimi-only).  
Without A4, Phase 1.3 is `logs_unavailable`.
