# SOP: Optimize one provider

This is a **research process for one vendor**, not a feature
checklist and not a FLOW.md template.

## Non-negotiable: do not generalize

**Every provider has a different character.** Most work already
done in this repo proves that — similarities are the exception.

Do **not** treat a finished peer (Groq, NVIDIA, Cohere, Voyage,
Morph, …) as a blueprint for the next folder. Do **not** mass-edit
other providers while fixing one. Do **not** invent shared
abstractions “because the SOP is the same.”

What usually differs (even when two vendors both say “OpenAI
compatible”):

| Area | Why peers diverge |
|------|-------------------|
| Auth / host | Bearer vs OAuth vs cookie vs query `key`; chat host ≠ native embed/rerank/audio host |
| Catalog | Live `/models`, hardcoded docs catalog, SQL table, or connection blob debt |
| Rate limits | Per key, IP, org, model, or endpoint; RPM/TPM/TPD/credits/calls; headers always / on 429 / never |
| Request body | Field names and shapes (`dimensions` vs `output_dimension`, `top_n` vs `top_k`, role maps, …) |
| Response body | Usage keys (`prompt_tokens` vs `total_tokens`), result arrays (`data` vs `results`), headers |
| Quota UX | Summary bars only, per-model modal, free-token grants, or “nothing published — stop” |
| Verbs | Chat-only vs embed+rerank vs TTS/STT — verify the verbs **this** vendor exposes |

A green `MODEL_CATALOG_TABLE` with broken proxy (503, wrong body,
wrong usage) is a **failed** optimization. Optimization means the
**full path for this vendor**: alias resolve, connection pool,
enabled catalog rows, headers, body sanitize / param map, upstream
URL, errors/fallback, `usage_history`, and every handler verb that
provider actually implements — not “catalog + quota.py only.”

Invariant (AGENTS.md): a missing `FLOW.md` is better than a shared
template. Write FLOW.md only from **this** provider's official
docs, user-reported behavior, and the code in
`backend/app/providers/<id>/`.

Contrast examples (read to see how different they are — **never
clone**): `alims-intl`, `cerebras`, `cohere`, `groq`, `jina-ai`,
`mistral`, `morph`, `nvidia`, `openrouter`, `voyage-ai`.

---

## 0. Freeze scope

Work **one** provider id (`config.PROVIDER_ID`, folder
`backend/app/providers/<id>/`).

Ask the user before coding:

- Which provider?
- Full path, or a named slice (catalog, quota, handler/wire,
  FLOW.md-only)? Default assumption is **full path** unless they
  narrow it.
- Any first-hand 429 / header / farm / custom `baseUrl` notes?
- Which verbs matter (chat, embeddings, rerank, audio, …)?

Stop if the provider is unclear or they asked to “do it like X.”
Restate that this vendor may have no published table, no live
headers, different units, and different request/response fields.

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
| Request fields | Verbatim names this API accepts / rejects |
| Response fields | Usage keys, result array name, error shape |
| Scope of limits | Per key, per IP, per org, per model, per endpoint |
| Units | RPM, RPD, TPM, TPD, IPM, credits, $, calls/month |
| When remaining is visible | Every response, 429 only, console only, never |
| Header / body field names | Copy **verbatim** |
| Plan names | Trial vs production — map later; do not invent |
| Unpublished | Write "not published" — do not fill gaps from another vendor |

Save a local snapshot under `.scratch/` only if the page is long or
likely to change. Register the scratch dir in `.gitignore` first.
Never write to `/tmp`.

If two official pages disagree, quote both and ask the user. Do not
pick silently.

---

## 2. User experience (only for cases docs omit)

Official docs win when they state a fact. Use operator notes when
docs are silent or wrong in production.

Typical UX inputs (ask; do not assume):

- A real 429 body / headers from this host
- Success responses that omit rate-limit headers
- Custom `baseUrl` / workspace host that must keep working
- Farm/bulk fields that exist in their export
- Model ids that 422 or "not enabled" on a whole farm
- Ban-risk of polling a usage/credits API (`GET /key`, dashboard)
- Playground / client params that upstream rejects (e.g. wrong
  dimension or top-N field name)

Label every UX claim in the brief and in FLOW.md as
`operator: <date>` so it is not mistaken for vendor docs.

If UX contradicts official docs, keep both, implement the safer
behavior, and say so.

---

## 3. Read this provider only

In order:

1. `backend/app/providers/<id>/` (config, handler, models, quota,
   bulk — whatever exists).
2. `_reference/` for the same provider if the folder exists.
   Faithful port: do not redesign unless the user asked.
3. Generic call sites (proxy, quota registry) only to see how
   hooks work. Do **not** add `if provider == ...` in routers,
   services, or frontend (PS Rule).

Provider-specific param maps and URL builders live **in that
provider's handler**, even when the client-facing `/v1/*` shape is
shared.

Do not borrow RATE_LIMITS keys, header maps, bar names, body field
maps, or merge logic from a sibling folder unless **this** vendor's
official docs use the same strings.

---

## 4. Write a per-provider brief (before code)

A short note is enough (plan file or `.scratch/<id>-opt-brief.md`).
It must answer **this vendor**, with sources:

1. What verbs does this provider expose?
2. Request/response field quirks vs the unified `/v1/*` client?
3. What is the limit scope and unit?
4. Does a published numeric table exist? Exact model / endpoint
   ids (same as `provider_models` / `usage_history`).
5. Do success responses carry remaining? 429 only? Never?
6. Is there a usage API? If yes, is polling it acceptable?
7. What should `fetch` show when headers never arrive?
8. Catalog: already `MODEL_CATALOG_TABLE`? Blob `data.models`?
9. What we will **not** build (and why).

If any answer is "same as Groq/NVIDIA/Voyage/…", rewrite it from
this vendor's docs. That sentence is a smell.

Show the brief to the user when two interpretations exist.

---

## 5. Decide the slice (do not assume one shape)

Finished providers did **not** get the same shape — that is the
point:

| Provider | Why it is not a template |
|----------|--------------------------|
| Groq | Org + per-model table; headers on **every** chat |
| NVIDIA | ~40 RPM per **key**; no per-model table; headers rare |
| OpenRouter | `:free` caps per **egress IP**; headers mainly on 429 |
| Cerebras | Org + model; free vs payg use **different bar kinds** |
| Mistral | **No** public numeric table; empty `RATE_LIMITS` is correct |
| Cohere | Chat per **model**; rerank/embed per **endpoint**; trial 1000/month |
| Alims Intl | Large Singapore Model Studio table; summary + on-demand detail |
| Voyage AI | Docs catalog (no `/models`); embed `dimensions`→`output_dimension`; rerank `top_n`→`top_k`; local free-token + RPM/TPM |
| Jina AI | One key, four kinds, three hosts (api/s/r); live `/models` + synthetic search/reader; local free-token grant + embed/rerank RPM/TPM card; do not split search/reader providers |

Possible outcomes when the user narrows scope:

- Catalog table only
- Quota from local `usage_history` only
- Quota from official headers / usage API
- Handler/wire / param-map fix only
- FLOW.md only (code already matches docs)
- **Nothing** — docs unpublished and no UX; say so and stop

Otherwise prefer the full path for that vendor's verbs.

Project rules that still apply:

- Catalog → `provider_models` (`MODEL_CATALOG_TABLE`). Never write
  the model list into connection `data`.
- Quota snapshot → `quota_cache`. Usage counts → `usage_history`.
- Connection `data` = secrets / health / `accountType` / `baseUrl`.
  No new credential columns on `provider_connections`.
- Logic in `backend/app/providers/<id>/` only (PS Rule).
- **Static constants → `config.py`** (audit): hosts, default /
  probe model ids, return-format maps, UI→docs plan maps,
  synthetic catalog rows, `RATE_LIMITS`, `LEGACY_IDS`,
  `EXTRA_HEADERS`. `handler.py` / `models.py` / `quota.py` read
  them; they must not redefine module-level `_FORMAT_MAP`,
  `_WEB_CATALOG`, `_UI_TO_DOCS_PLAN`, or duplicate host/model
  string literals. That is what `config.py` is for — one file to
  open when values change.
- **Public vs private names:** leading `_` means private to the
  defining module. If another file (sibling provider module,
  router, or test of the public API) must import a function or
  constant, give it an unprefixed name. Keep `_` only for
  helpers that stay inside that file.
- Frontend metadata from `/providers/catalog` (`catalogStore`).
- Generic hooks (ListTree, observe, usage token fallbacks that
  help **all** vendors) are fine; a hardcoded `provider === 'foo'`
  in a shared page is not. Prefer catalog flags for new UI gates.

---

## 6. Implement

Primary edits: this provider folder, its tests, and its FLOW.md.

Also allowed when required by **this** vendor's contract:

- Generic proxy usage normalization that does not hardcode the
  provider id (e.g. map `total_tokens` → tracked prompt tokens).
- Catalog / Quota Tracker UI that already keys off handler
  capabilities, not an allowlist of ids.

Do **not** turn on `MODEL_CATALOG_TABLE` for unrelated providers
in the same change. Historical OpenRouter notes live under
`docs/architecture/2026-08-15-openrouter-catalog-slice.md` —
read if relevant; do not treat as a required checklist item.

`RATE_LIMITS` rules:

- Keys = exact upstream / catalog ids (or a documented
  `accountType/` prefix if **this** provider uses that scheme).
- Omit rows the vendor does not publish.
- Convert units only when the official page defines the conversion.
- Do not invent `tpd` because Groq has `tpd`.

Quota rules:

- `USES_UPSTREAM` is true only if this handler actually polls an
  upstream usage API.
- Overlay live headers onto local bars **only** when names (or an
  explicit map documented for this vendor) match.
- If success rarely sends headers, a stale 429 snapshot must not
  pin a bar (TTL or ignore). Reuse an **idea** from another
  provider only after this vendor has the same failure mode.
- Bar labels are this vendor's language.

Handler rules:

- Build URLs from **this** host's path contract (from `config.py`,
  not a hardcoded host string in the handler).
- Map unified client params to **this** vendor's field names in
  the handler (never assume Cohere/OpenAI names work upstream).
- Native endpoints stay native. Do not force everything through
  chat completions.
- Keep static maps/defaults on the config class; handler only
  applies them.

Tests: `cd backend && uv run pytest …` (host venv `backend/.venv`).

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
- Proxy verbs this handler actually implements (and param maps)
- Catalog
- Quota (`fetch`, `observe`, detail modal — only if present)
- Implementation notes unique to this vendor

Do **not** paste another provider's Files table, header list,
param map, or merge paragraph and edit names.

After any later code change in that folder, update the same
FLOW.md in the same change.

---

## 8. Verify

- Unit tests for new helpers / quota rows / handler body maps.
- ProviderDetailPage (or media kind page) for this id: connect or
  open a connection, fetch models if catalog moved.
- Exercise the **verbs this provider exposes** (chat and/or
  embeddings and/or rerank and/or audio) — not a default “cheap
  chat” if the vendor is embed/rerank-only.
- Quota Tracker only if this provider now has a handler: bars
  match the brief; empty connection is not a huge payload.
- `rg` the diff: no new `if provider ==` outside this folder.
- Audit statics: `rg` module-level `_…_MAP` / host / default-model
  literals in `handler.py` / `models.py` / `quota.py` — move any
  hits into `config.py`.
- Audit naming: names imported across files must be unprefixed;
  `_` only for same-file private helpers.

Report what you did **not** verify (no live 429, no console
login, …).

Do not commit unless the user asks.

---

## 9. Anti-patterns

- "Same as NVIDIA/Groq/Voyage" RATE_LIMITS, headers, bar titles,
  or request/response field maps
- Copy-pasting a sibling `quota.py` / `FLOW.md` and renaming
- Filling unpublished caps with guessed numbers
- Marketing model names that never appear in `/models` or logs
- A shared FLOW.md skeleton checked into `docs/`
- Polling a credits/usage API the user flagged as ban-risk
- Dual-writing catalog into `data.models`
- Frontend provider allowlists when a catalog flag would do
- Optimizing two providers in one PR "because the SOP is the same"
- Calling the work done after only flipping `MODEL_CATALOG_TABLE`
- Scattering static `_FORMAT_MAP` / `_WEB_CATALOG` /
  `_UI_TO_DOCS_PLAN` / host or default-model strings across
  handler/models/quota instead of `config.py`
- Exporting a cross-file API under a leading `_` name (Python
  private); rename to a public identifier if other modules import
  it

---

## 10. Suggested command trail

```bash
# Host venv — same as local uvicorn
cd backend
uv run pytest tests/test_quota_handlers.py -k '<id>' -v
# plus provider-specific body/catalog tests when you add them
```

Official pages change. Re-read the URL in step 1 on every new
slice; do not trust a FLOW.md older than the retrieve date you
are about to publish.
