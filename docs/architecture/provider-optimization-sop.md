# SOP: Optimize one provider (catalog, quota, FLOW.md)

This is a **research process**, not a feature checklist and not a
FLOW.md template. Copying Groq, NVIDIA, OpenRouter, or Cohere into
another folder is a defect.

Invariant (AGENTS.md): a missing `FLOW.md` is better than a shared
template. Write FLOW.md only from **this** provider's official
docs, user-reported behavior, and the code in
`backend/app/providers/<id>/`.

Done examples (for contrast, not cloning): `alims-intl`, `cerebras`,
`cohere`, `groq`, `mistral`, `nvidia`, `openrouter`.

---

## 0. Freeze scope

Work **one** provider id (`config.PROVIDER_ID`, folder
`backend/app/providers/<id>/`).

Ask the user before coding:

- Which provider?
- What slice? Catalog table, quota tracker, handler/wire fix,
  FLOW.md-only, or a mix they named.
- Any first-hand 429 / header / farm / custom `baseUrl` notes?

Stop if the provider is unclear or they asked to "do it like Groq".
Restate that this vendor may have no published table, no live
headers, or a different unit (credits, seats, org, IP).

Do not start a second provider in the same change set.

---

## 1. Official documentation first

Find the vendor's **current** public docs. Prefer the vendor site
over blogs, Discord, or another provider's FLOW.md.

Record in the later brief (and in FLOW.md sources):

| Field | Fill from the official page |
|-------|-----------------------------|
| URL | Exact page, not the marketing home |
| Retrieved | Date you read it (`YYYY-MM-DD`) |
| Auth | Bearer key, OAuth, cookie, query `key`, none |
| Host / base path | Chat vs native (rerank, embed, audio) may differ |
| Scope of limits | Per key, per IP, per org, per model, per endpoint |
| Units | RPM, RPD, TPM, TPD, IPM, credits, $ , calls/month |
| When remaining is visible | Every response, 429 only, console only, never |
| Header / body field names | Copy **verbatim** (`x-ratelimit-remaining-requests` ≠ `x-ratelimit-remaining`) |
| Plan names | Trial vs production vs Scale — map later; do not invent |
| Unpublished | Write "not published" — do not fill gaps from another vendor |

Save a local snapshot under `.scratch/` only if the page is long or
likely to change (example: `.scratch/alibaba-studio-ratelimit.md`).
Register the scratch dir in `.gitignore` first. Never write to
`/tmp`.

If two official pages disagree, quote both and ask the user. Do not
pick silently.

---

## 2. User experience (only for cases docs omit)

Official docs win when they state a fact. Use operator notes when
docs are silent or wrong in production.

Typical UX inputs (ask; do not assume):

- A real 429 body / headers from this host
- Success chats that omit rate-limit headers
- Custom `baseUrl` / workspace host that must keep working
- Farm/bulk fields that exist in their export
- Model ids that 422 or "not enabled" on a whole farm
- Ban-risk of polling a usage/credits API (`GET /key`, dashboard)

Label every UX claim in the brief and in FLOW.md as
`operator: <date>` so it is not mistaken for vendor docs.

If UX contradicts official docs, keep both, implement the safer
behavior, and say so. Example: NVIDIA docs mention ~40 RPM; success
and many 429s omit `X-RateLimit-*` — tracker `used` comes from
`usage_history`, not from a missing header.

---

## 3. Read this provider only

In order:

1. `backend/app/providers/<id>/` (config, handler, models, quota,
   bulk — whatever exists).
2. `_reference/` for the same provider if the folder exists. Faithful
   port: do not redesign unless the user asked.
3. Call sites that are generic (proxy `build_headers`, quota
   registry). Do **not** add `if provider == ...` in routers,
   services, or frontend.

Do not "borrow" RATE_LIMITS keys, header maps, bar names, or merge
logic from a sibling folder unless the official docs use the same
strings.

---

## 4. Write a per-provider brief (before code)

A short note is enough (plan file or `.scratch/<id>-opt-brief.md`).
It must answer **this vendor**, with sources:

1. What is the limit scope and unit?
2. Does a published numeric table exist? If yes, exact model /
   endpoint ids (same ids as `provider_models` / `usage_history`,
   not marketing names).
3. Do success responses carry remaining? 429 only? Never?
4. Is there a usage API? If yes, is polling it acceptable?
5. What should `fetch` show when headers never arrive?
6. Catalog: already `MODEL_CATALOG_TABLE`? Blob `data.models`?
7. Handler quirks (role map, native rerank host, TTS path).
8. What we will **not** build (and why).

If any answer is "same as Groq/NVIDIA/…", rewrite it from this
vendor's docs. That sentence is a smell.

Show the brief to the user when two interpretations exist.

---

## 5. Decide the slice (do not assume all four)

The seven done providers did **not** get the same shape:

| Provider | Why it is not a template |
|----------|--------------------------|
| Groq | Org + per-model table; headers on **every** chat |
| NVIDIA | ~40 RPM per **key**; no per-model table; headers rare |
| OpenRouter | `:free` caps per **egress IP**; headers mainly on 429 |
| Cerebras | Org + model; free vs payg use **different bar kinds** |
| Mistral | **No** public numeric table; empty `RATE_LIMITS` is correct |
| Cohere | Chat per **model**; rerank/embed per **endpoint**; trial 1000/month |
| Alims Intl | Large Singapore Model Studio table; summary fetch + on-demand detail |

Possible outcomes for the next provider:

- Catalog table only
- Quota from local `usage_history` only
- Quota from official headers / usage API
- Handler/wire fix only
- FLOW.md only (code already matches docs)
- **Nothing** — docs unpublished and no UX; say so and stop

Project rules that still apply whatever the slice:

- Catalog → `provider_models` (`MODEL_CATALOG_TABLE`). Never write
  the model list into connection `data`.
- Quota snapshot → `quota_cache`. Usage counts → `usage_history`.
- Connection `data` = secrets / health / `accountType` / `baseUrl`.
  No new credential columns on `provider_connections`.
- Logic in `backend/app/providers/<id>/` only (PS Rule).
- Frontend metadata from `/providers/catalog` (`catalogStore`).
- A generic hook (ListTree, observe) is allowed; a hardcoded
  `provider === 'foo'` in a shared page is not, unless the user
  already accepted that pattern for a previous provider **and**
  this vendor needs the same UI affordance. Prefer catalog flags
  when adding a new UI gate.

---

## 6. Implement

Touch only this provider folder, its tests, and its FLOW.md.
Update `docs/architecture/2026-08-15-openrouter-catalog-slice.md`
if you turn `MODEL_CATALOG_TABLE` on.

`RATE_LIMITS` rules:

- Keys = exact upstream / catalog ids (or a documented
  `accountType/` prefix if **this** provider uses that scheme).
- Omit rows the vendor does not publish.
- Convert units only when the official page defines the conversion
  (example: Alims RPS → RPM × 60 because **their** table lists RPS).
- Do not invent `tpd` because Groq has `tpd`.

Quota rules:

- `USES_UPSTREAM` is true only if this handler actually polls an
  upstream usage API.
- Overlay live headers onto local bars **only** when names (or an
  explicit map documented for this vendor) match.
- If success rarely sends headers, a stale 429 snapshot must not
  pin a bar (TTL or ignore). Copy the **idea** from Mistral/NVIDIA
  only after this vendor has the same failure mode.
- Bar labels are this vendor's language (`NIM requests…`,
  `Mistral RPM (per minute)`, `{model} tokens (TPD)`).

Handler rules:

- Build URLs from **this** host's path contract. A default
  `BASE_URL` that already includes `/v1` or `/compatible-mode/v1`
  must not grow a second copy of that suffix.
- Native endpoints (Cohere `/v1/rerank`, NVIDIA `/audio/speech`)
  stay native. Do not force everything through chat completions.

Tests: `cd backend && PYTHONPATH=. .venv/bin/pytest …` (or
`uv run pytest`). Host venv is `backend/.venv`.

---

## 7. Write `FLOW.md` last

Create `backend/app/providers/<id>/FLOW.md` after the code matches
the brief.

Source of truth = files in **this** folder + the official URLs and
operator notes from steps 1–2. If a sentence cannot be pointed at
one of those, delete it.

Include only sections that exist for this provider. Typical
(optional) blocks:

- Identity / hosts / auth
- Files in this folder and what each one does
- Rate limits, with the official URL and retrieve date
- Proxy chat (and other verbs this handler actually implements)
- Catalog
- Quota (`fetch`, `observe`, detail modal — only if present)
- Implementation notes unique to this vendor

Do **not** paste another provider's Files table, header list, or
merge paragraph and edit names.

After any later code change in that folder, update the same
FLOW.md in the same change.

---

## 8. Verify

- Unit tests for the new helpers / quota rows / handler behavior.
- ProviderDetailPage for this id: connect or open an existing
  connection, fetch models if catalog moved, send a cheap test
  chat if the slice touches proxy/headers.
- Quota Tracker only if this provider now has a handler: bars
  match the brief; empty/unused connection is not a 1 MB payload.
- `rg` the diff: no new `if provider ==` outside this folder.

Report what you did **not** verify (no live 429, no official
console login, …).

Do not commit unless the user asks.

---

## 9. Anti-patterns

- "Same as NVIDIA/Groq" RATE_LIMITS, header names, or bar titles
- Filling unpublished caps with guessed numbers
- Marketing model names that never appear in `/models` or logs
- A shared FLOW.md skeleton checked into `docs/`
- Polling a credits/usage API the user flagged as ban-risk
- Dual-writing catalog into `data.models`
- Frontend provider allowlists when a catalog flag would do
- Optimizing two providers in one PR "because the SOP is the same"

---

## 10. Suggested command trail

```bash
# Host venv — same as local uvicorn
cd backend
.venv/bin/pytest tests/test_quota_handlers.py -k '<id>' -v
# or: uv run pytest tests/test_quota_handlers.py -k '<id>' -v
```

Official pages change. Re-read the URL in step 1 on every new
slice; do not trust a FLOW.md older than the retrieve date you
are about to publish.
