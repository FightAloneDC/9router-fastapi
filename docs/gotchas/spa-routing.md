# Gotchas: SPA routing vs API

Production serves UI and API from the same FastAPI process. Several URL
collisions are easy to hit.

## Browser refresh returns `{"detail":"Not authenticated"}`

**Symptom:** `/providers` (or `/settings`, `/usage`, …) works when navigating
inside the app, but a full refresh shows JSON 401.

**Cause:** Those paths exist as authenticated API routes. A browser refresh
sends `Accept: text/html`; without SPA handling, FastAPI runs the API route.

**Fix (already in code):** `SpaHtmlMiddleware` serves `index.html` when the
client prefers HTML. Axios (`Accept: application/json` first) still hits API
via `/api/...`.

## Provider icons flood 401 in the console

**Symptom:** Many `GET /providers/xxx.png` → 401.

**Cause:** `<img src="/providers/{id}.png">` matched `/providers/{conn_id}`
(auth required) instead of static files.

**Fix (already in code):** `mount_provider_icons` registers
`/providers/{name}.png` before provider API routes.

## OpenAPI `/docs` missing in production

Expected when `DEBUG=false`. Set `DEBUG=true` in `backend/.env` and
recreate the backend container to enable Swagger for debugging.

## Dual `/api` and bare API paths

- Dashboard axios → `/api/...` → middleware strips `/api`
- OpenAI clients → `/v1/...` (no `/api` prefix)
- Do not assume bare `/providers` in the browser is always the API
