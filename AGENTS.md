# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For
trivial tasks, use judgment.

Project architecture, stack, runbooks, and debugging live under
[`docs/`](docs/README.md) — especially
[`docs/architecture/handbook.md`](docs/architecture/handbook.md).
Do not grow this file into a project encyclopedia.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick
  silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?"
If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's
request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make
  them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it
  pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria
("make it work") require constant clarification.

## 5. Language Rules (MANDATORY)

- **Code and documentation: ALWAYS English.** Every file, skill,
  config, comment, variable name, function name, doc, README —
  English only. No exceptions.
- **Communication with user: ALWAYS Indonesian.** All conversation,
  explanations, questions, and responses in Bahasa Indonesia.
- **This rule has been stated hundreds of times. Do not forget.
  Do not violate.**

---

**These guidelines are working if:** fewer unnecessary changes in
diffs, fewer rewrites due to overcomplication, and clarifying
questions come before implementation rather than after mistakes.

---

## 6. Project invariants (9Router)

Short rules only. Details: [`docs/architecture/handbook.md`](docs/architecture/handbook.md).

1. **Faithful port** — Read `_reference/` before changing behavior;
   do not redesign unless asked.
2. **Catalog/quota are SQL** — Model lists → `provider_models`
   (`MODEL_CATALOG_TABLE`). Quota → `quota_cache`. Usage →
   `usage_history`. Connection `data` is secrets/health only — never
   the model catalog; no new credential columns on
   `provider_connections`.
3. **PS Rule** — Provider-specific logic lives in
   `backend/app/providers/<id>/` only. No hardcoded provider checks
   in routers, services, or frontend.
4. **catalogStore** — Frontend provider metadata comes from
   `/providers/catalog`. Do not hardcode provider lists.
5. **Provider FLOW.md** — Per-provider flow from that provider's
   code only. Update after changes; missing FLOW.md beats a shared
   template. Process:
   [`docs/architecture/provider-optimization-sop.md`](docs/architecture/provider-optimization-sop.md).
6. **Provider detail UI** — `/providers/:id`
   (`ProviderDetailPage`) is canonical. `/media-providers/:kind/:id`
   must follow that UI; only kind-scoped differences allowed.
   Providers menu features must work end-to-end; verify in the
   running app. See `.cursor/rules/provider-detail-ui.mdc`.
7. **Optimistic UI** — Toggle state first, then API; rollback on
   failure.
8. **Docker hot reload** — Do not rebuild containers for ordinary
   code edits (volume mounts).
9. **Backups** — Files with `-v*` suffix are intentional; do not
   delete or edit them.
10. **No agent trash** — Register scratch dirs in `.gitignore`
    before creating them. Never force-add ignored paths. No
    `/tmp` test artifacts (host uptime is long).

## 7. Global Rules

- Do not auto-commit, push, or tag without explicit permission
- Do not delete files without asking first
- Ask before judging existing configuration as broken
- Do not expand scope beyond the specified focus
- Report outcomes; do not claim success before testing
- Prefer reading existing code before making changes
- If a file exceeds ~200–300 lines, split or modularize
- Never write scratch/test scripts to `/tmp`

## 8. Python Rules (Backend — FastAPI)

- Use `backend/.venv` (or `uv run` in `backend/`). Never
  a system Python. Do not create repo-root extra venvs
  (`.venv-test`, `.venv-local`).
- Type annotations on all function parameters and return values
- Prefer stdlib over third-party packages
- Max 80 characters per line
- Guard clause pattern (early return)
- snake_case / UPPER_CASE for constants
- One function = one responsibility
- Import order: stdlib, third-party, local (blank line between)
- async/await for DB and HTTP
- Pydantic for request/response validation
- Alembic for schema changes — never edit tables by hand

## 9. JavaScript Rules (Frontend — React/Vite)

- Prefer const over let; never var
- async/await over callbacks / `.then()`
- ESLint config must be present
- Max 80 characters per line
- Destructure imports when possible
- Zustand for global state — no prop drilling for globals
- Components in `src/components/`, pages in `src/pages/`
- API calls in `src/api/` modules

## 10. Tooling

- Never edit upstream packages (`node_modules`, `vendor/`, …)
- Use `uv` for Python deps and scripts
- Scratch files stay in the workdir (e.g. `tests/`, `.scratch/`)


---

## enowx-rag memory

This project uses the `enowx-rag` MCP server for per-project memory.

### Before coding

1. Call `rag_retrieve_context` with the project ID `9router-fastapi` and the user's query.
2. Read the returned context. If relevant, use it to shape your answer or plan.

### After coding

1. Summarize what you changed.
2. Call `rag_index` with useful new facts, design decisions, gotchas, or patterns under project ID `9router-fastapi`.

Keep chunks concise (one idea per chunk). Use metadata tags like `type:architecture`, `type:decision`, `type:api`, `type:bugfix`, `type:howto`, or `type:snippet`.

