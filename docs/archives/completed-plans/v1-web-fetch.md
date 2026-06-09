# Plan: POST /v1/web/fetch

**Status:** Not started  
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Original source:** `~/dev/9router/src/app/api/v1/web/fetch/route.js` → `src/sse/handlers/fetch.js` → `open-sse/handlers/fetch/index.js`  
**Estimated effort:** Low — only 4 provider adapters, all straightforward HTTP requests, no async polling or streaming.

---

## What This Does

Adds a web content extraction endpoint to the FastAPI proxy. Clients send a
URL + provider, 9Router routes to the appropriate web scraping/extraction API,
and returns the page content in a normalized format.

```
Client → POST /v1/web/fetch { model: "tavily", url: "https://example.com" }
           ↓
       resolve provider → "tavily" (web fetch API)
           ↓
       POST https://api.tavily.com/extract { urls: ["https://example.com"] }
           ↓
       normalize response → unified FetchResult format
           ↓
       return { provider, url, title, content: { format, text, length }, metrics }
```

---

## Key Characteristics

1. **Provider IS the model** — same pattern as `/v1/search`. `body.model` or
   `body.provider` identifies the web fetch provider.

2. **Only 4 providers** — the simplest endpoint in terms of adapter count:
   firecrawl, jina-reader, tavily, exa.

3. **No async polling** — all providers return results synchronously (unlike
   image generation or search).

4. **No streaming** — all responses are standard JSON.

5. **Content truncation** — `max_characters` parameter limits response size.
   Important for large pages.

6. **Unified response format** — all providers normalize to:
   ```json
   {
     "provider": "tavily",
     "url": "https://example.com",
     "title": "Example Domain",
     "content": { "format": "markdown", "text": "...", "length": 5000 },
     "metadata": { "author": null, "published_at": null, "language": null },
     "usage": { "fetch_cost_usd": 0.008 },
     "metrics": { "response_time_ms": 450, "upstream_latency_ms": 420 }
   }
   ```

---

## Supported Providers

| Provider      | Upstream URL                                    | Method | Auth Header   | Request Body                          | Response Shape                              |
|--------------|------------------------------------------------|--------|---------------|---------------------------------------|---------------------------------------------|
| firecrawl    | https://api.firecrawl.dev/v1/scrape            | POST   | Bearer        | `{ url, formats: ["markdown"] }`      | `{ data: { markdown, html, metadata } }`    |
| jina-reader  | https://r.jina.ai/{encoded_url}                | GET    | Bearer        | (none — URL in path)                  | Raw text (markdown with title as `# Title`) |
| tavily       | https://api.tavily.com/extract                 | POST   | Bearer        | `{ urls: [url], extract_depth }`      | `{ results: [{ raw_content }] }`            |
| exa          | https://api.exa.ai/contents                    | POST   | x-api-key     | `{ ids: [url], text: true }`          | `{ results: [{ title, text }] }`            |

### Provider Details

**Firecrawl** — Professional web scraping API. Returns markdown, HTML, or
plain text. Handles JavaScript-rendered pages. Has metadata extraction
(title, author, language). Most feature-rich but costs $0.002/request.

**Jina Reader** — Free web reader API. Returns markdown by default. No request
body needed — URL is part of the path. Title extracted from first `# heading`
in the response. Free tier: 1M requests/month.

**Tavily Extract** — Part of Tavily's search API. Extracts raw content from
URLs. Simple API but returns `raw_content` without title. Costs $0.008/request.

**Exa Contents** — Part of Exa's search API. Returns full text + title. Uses
`x-api-key` auth (different from Bearer). Costs $0.001/request.

---

## Request / Response Format

**Request:**
```json
POST /v1/web/fetch
Authorization: Bearer <jwt_or_api_key>
Content-Type: application/json

{
  "model": "tavily",
  "url": "https://example.com/article",
  "format": "markdown",
  "max_characters": 10000
}
```

- `model` or `provider` (required) — provider alias or ID (tavily, exa, firecrawl, jina-reader)
- `url` (required) — the URL to fetch/extract content from
- `format` (optional) — output format: `markdown` (default), `text`, `html`
- `max_characters` (optional) — max characters to return (default: provider-specific, usually 100000-200000)

**Response (unified format):**
```json
{
  "provider": "tavily",
  "url": "https://example.com/article",
  "title": "Article Title",
  "content": {
    "format": "markdown",
    "text": "# Article Title\n\nFull page content in markdown...",
    "length": 5000
  },
  "metadata": {
    "author": "John Doe",
    "published_at": "2026-05-20",
    "language": "en"
  },
  "usage": {
    "fetch_cost_usd": 0.008
  },
  "metrics": {
    "response_time_ms": 450,
    "upstream_latency_ms": 420
  }
}
```

---

## Phase 1 — Backend: Web Fetch Adapters

**New file:** `backend/app/services/fetch_adapters.py`

Only 4 adapters. Each returns the unified response shape directly.

### 1.1 Shared Utilities

```python
import time

DEFAULT_TIMEOUT_S = 15
DEFAULT_FORMAT = "markdown"

def truncate(text: str, max_chars: int | None) -> str:
    """Truncate text to max characters."""
    if not text or not isinstance(text, str):
        return ""
    if not max_chars or max_chars <= 0:
        return text
    return text[:max_chars] if len(text) > max_chars else text

def build_response(provider: str, url: str, title: str | None, format: str,
                   text: str, cost_usd: float | None, response_ms: int,
                   upstream_ms: int) -> dict:
    """Build unified fetch response."""
    return {
        "provider": provider,
        "url": url,
        "title": title,
        "content": {"format": format, "text": text or "", "length": len(text or "")},
        "metadata": {"author": None, "published_at": None, "language": None},
        "usage": {"fetch_cost_usd": cost_usd},
        "metrics": {"response_time_ms": response_ms, "upstream_latency_ms": upstream_ms},
    }

def parse_jina_title(text: str) -> str | None:
    """Extract title from Jina markdown response (first # heading)."""
    import re
    match = re.search(r"^\s*#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None
```

### 1.2 Firecrawl Adapter

```python
async def fetch_firecrawl(
    client: httpx.AsyncClient,
    api_key: str,
    url: str,
    format: str = "markdown",
    max_characters: int = None,
) -> dict:
    """Firecrawl — professional web scraping API."""
    start = time.time()
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    body = {"url": url, "formats": [format]}
    
    resp = await client.post(
        "https://api.firecrawl.dev/v1/scrape",
        json=body, headers=headers,
    )
    upstream_ms = int((time.time() - start) * 1000)
    resp.raise_for_status()
    
    data = resp.json().get("data", {})
    text = truncate(
        data.get("markdown") or data.get("html") or data.get("text", ""),
        max_characters,
    )
    title = (data.get("metadata") or {}).get("title")
    
    return build_response(
        provider="firecrawl", url=url, title=title, format=format,
        text=text, cost_usd=0.002,
        response_ms=int((time.time() - start) * 1000), upstream_ms=upstream_ms,
    )
```

### 1.3 Jina Reader Adapter

```python
async def fetch_jina_reader(
    client: httpx.AsyncClient,
    api_key: str,
    url: str,
    format: str = "markdown",
    max_characters: int = None,
) -> dict:
    """Jina Reader — free web content extraction."""
    from urllib.parse import quote
    
    start = time.time()
    target = f"https://r.jina.ai/{quote(url, safe='')}"
    
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    resp = await client.get(target, headers=headers)
    upstream_ms = int((time.time() - start) * 1000)
    resp.raise_for_status()
    
    body = await resp.aread()
    text = truncate(body.decode("utf-8", errors="replace"), max_characters)
    title = parse_jina_title(text)
    
    return build_response(
        provider="jina-reader", url=url, title=title, format=format,
        text=text, cost_usd=0.0,
        response_ms=int((time.time() - start) * 1000), upstream_ms=upstream_ms,
    )
```

### 1.4 Tavily Extract Adapter

```python
async def fetch_tavily(
    client: httpx.AsyncClient,
    api_key: str,
    url: str,
    format: str = "markdown",
    max_characters: int = None,
) -> dict:
    """Tavily Extract — web content extraction."""
    start = time.time()
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    body = {"urls": [url], "extract_depth": "basic"}
    
    resp = await client.post("https://api.tavily.com/extract", json=body, headers=headers)
    upstream_ms = int((time.time() - start) * 1000)
    resp.raise_for_status()
    
    data = resp.json()
    first = (data.get("results") or [{}])[0]
    text = truncate(first.get("raw_content", ""), max_characters)
    
    return build_response(
        provider="tavily", url=url, title=None, format=format,
        text=text, cost_usd=0.008,
        response_ms=int((time.time() - start) * 1000), upstream_ms=upstream_ms,
    )
```

### 1.5 Exa Contents Adapter

```python
async def fetch_exa(
    client: httpx.AsyncClient,
    api_key: str,
    url: str,
    format: str = "markdown",
    max_characters: int = None,
) -> dict:
    """Exa Contents — full text extraction from URLs."""
    start = time.time()
    
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    body = {"ids": [url], "text": True}
    
    resp = await client.post("https://api.exa.ai/contents", json=body, headers=headers)
    upstream_ms = int((time.time() - start) * 1000)
    resp.raise_for_status()
    
    data = resp.json()
    first = (data.get("results") or [{}])[0]
    text = truncate(first.get("text", ""), max_characters)
    title = first.get("title")
    
    return build_response(
        provider="exa", url=url, title=title, format=format,
        text=text, cost_usd=0.001,
        response_ms=int((time.time() - start) * 1000), upstream_ms=upstream_ms,
    )
```

### 1.6 Dispatch Table

```python
FETCH_ADAPTERS = {
    "firecrawl": fetch_firecrawl,
    "jina-reader": fetch_jina_reader,
    "tavily": fetch_tavily,
    "exa": fetch_exa,
}

def get_fetch_adapter(provider: str):
    return FETCH_ADAPTERS.get(provider)
```

---

## Phase 2 — Backend: URL Validation Helper

```python
from urllib.parse import urlparse

def validate_url(url: str) -> str | None:
    """Validate URL format. Returns error message or None if valid."""
    if not url or not isinstance(url, str):
        return "url is required"
    
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return "url must start with http:// or https://"
        if not parsed.netloc:
            return "url must have a valid domain"
    except Exception:
        return "Invalid URL format"
    
    return None
```

---

## Phase 3 — Backend: Add `/v1/web/fetch` Route

**File:** `backend/app/routers/v1_proxy.py`

```python
@router.post("/web/fetch")
async def web_fetch(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """Web content extraction proxy."""
    from app.services.fetch_adapters import get_fetch_adapter, validate_url
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    # Accept provider or model field
    provider_input = body.get("provider") or body.get("model")
    target_url = body.get("url")
    format = body.get("format", "markdown")
    max_characters = body.get("max_characters")
    
    if not provider_input:
        raise HTTPException(status_code=400, detail="Missing required field: provider (or model)")
    
    if not target_url:
        raise HTTPException(status_code=400, detail="Missing required field: url")
    
    # Validate URL
    url_error = validate_url(target_url)
    if url_error:
        raise HTTPException(status_code=400, detail=url_error)
    
    # Resolve provider
    provider_id = _resolve_provider_alias(provider_input)
    
    # Check adapter exists
    adapter = get_fetch_adapter(provider_id)
    if not adapter:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_id}' does not support web fetch. "
                   f"Supported: {', '.join(FETCH_ADAPTERS.keys())}",
        )
    
    # DB lookup for credentials
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.provider == provider_id, ProviderConnection.is_active == True)
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()
    
    if not connections:
        raise HTTPException(status_code=503, detail=f"No connection for provider: {provider_id}")
    
    # Try each connection (fallback loop)
    last_error = None
    for conn in connections:
        data = json.loads(conn.data) if conn.data else {}
        api_key = data.get("apiKey", "")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                result = await adapter(
                    client=client,
                    api_key=api_key,
                    url=target_url,
                    format=format,
                    max_characters=max_characters,
                )
            
            return JSONResponse(content=result)
        
        except httpx.HTTPStatusError as e:
            last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
            if e.response.status_code < 500:
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": e.response.text[:500]}},
                )
            continue
        except httpx.ConnectError as e:
            last_error = {"status": 503, "detail": str(e)}
            continue
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)}
            continue
    
    error_msg = last_error.get("detail", "All providers failed") if last_error else "No targets"
    error_status = last_error.get("status", 502) if last_error else 502
    return JSONResponse(
        status_code=error_status,
        content={"error": {"message": error_msg}},
    )
```

---

## Phase 4 — Frontend: No Changes Required

The `/v1/web/fetch` endpoint is a pure API endpoint. No UI changes needed.
MediaProvidersPage already shows web fetch providers.

---

## Phase 5 — Testing

### 5.1 Manual curl tests

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — Tavily Extract (happy path):**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tavily", "url": "https://example.com"}' \
  | jq '{provider, url, title, content_length: .content.length, format: .content.format}'
```
Expected: `provider: "tavily"`, `content_length > 0`.

**Test 2 — Jina Reader (no auth):**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "jina-reader", "url": "https://example.com"}' \
  | jq '{provider, title, content_length: .content.length}'
```
Expected: `provider: "jina-reader"`, title extracted from markdown.

**Test 3 — Exa Contents:**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "exa", "url": "https://example.com"}' \
  | jq '{provider, title, content_length: .content.length}'
```

**Test 4 — Firecrawl:**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "firecrawl", "url": "https://example.com"}' \
  | jq '{provider, title, content_length: .content.length}'
```

**Test 5 — With max_characters truncation:**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tavily", "url": "https://en.wikipedia.org/wiki/Artificial_intelligence", "max_characters": 500}' \
  | jq '{content_length: .content.length, text_preview: (.content.text[0:100])}'
```
Expected: `content_length <= 500`.

**Test 6 — Missing url (400):**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tavily"}' | jq .
```
Expected: `400` with `"Missing required field: url"`.

**Test 7 — Invalid URL (400):**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tavily", "url": "not-a-url"}' | jq .
```
Expected: `400` with `"url must start with http:// or https://"`.

**Test 8 — No connection (503):**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "nonexistent", "url": "https://example.com"}' | jq .
```
Expected: `503` or `400`.

**Test 9 — Unsupported provider (400):**
```bash
curl -s -X POST http://localhost:9000/v1/web/fetch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai", "url": "https://example.com"}' | jq .
```
Expected: `400` with `"Provider 'openai' does not support web fetch"`.

**Test 10 — Verify console log:**
```bash
curl -s http://localhost:9000/console/logs \
  -H "Authorization: Bearer $TOKEN" | jq '.[-1]'
```
Expected: log entry shows `POST /v1/web/fetch → 200`.

### 5.2 Regression check

```bash
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```

---

## Phase 6 — Report

1. **`docs/porting-status.md`** — Move `POST /v1/web/fetch` to "Fully Ported".
2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 7 as ✅.
3. **`docs/plans/v1-web-fetch.md`** (this file) — Update status to `Done`.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Firecrawl requires API key | Paid service ($0.002/request). Free tier: 500 requests/month. |
| Jina Reader free tier | 1M requests/month free. No API key required for basic usage. |
| Tavily Extract costs | $0.008/request. Same API key as Tavily Search. |
| Exa Contents costs | $0.001/request. Same API key as Exa Search. |
| Content truncation | Applied after fetching full content. Provider still pays for full extraction. |
| JavaScript-rendered pages | Only Firecrawl handles JS-rendered pages. Jina, Tavily, Exa return static HTML. |
| Rate limiting | None implemented in Phase 1. Providers have their own rate limits. |
| Crawl4AI | Listed in FastAPI constants but no adapter in original. Can be added later as a local/noAuth provider. |
| Combo expansion | The original supports combo expansion for web fetch. Not implemented in Phase 1. |
| `format` parameter | Only Firecrawl truly supports multiple formats (markdown, html, text). Others always return markdown/text. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/fetch_adapters.py` | NEW — 4 fetch adapters, URL validator, shared utils |
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/web/fetch` handler |
| `docs/porting-status.md` | Move web/fetch endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 7 done |
| `docs/plans/v1-web-fetch.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Route handler | Low | Simple JSON parsing, URL validation, provider dispatch |
| Firecrawl adapter | Low | POST request, JSON response |
| Jina Reader adapter | Low | GET request with URL in path, raw text response |
| Tavily adapter | Low | POST request, JSON response |
| Exa adapter | Low | POST request, different auth header |
| URL validation | Trivial | urlparse check |
| Content truncation | Trivial | String slicing |
| Error handling | Low | Standard HTTP error passthrough |

**Overall:** Low complexity — the simplest endpoint in the entire v1 proxy
surface. Only 4 adapters, all straightforward HTTP requests, no async polling,
no streaming, no binary responses. The unified response format is simple.

**Recommended implementation order:**
1. Jina Reader (no auth, simplest — GET request)
2. Tavily (POST, same API key as search)
3. Exa (POST, different auth header)
4. Firecrawl (POST, most feature-rich)
