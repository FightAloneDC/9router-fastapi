# Plan: POST /v1/search

**Status:** Not started  
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Original source:** `~/dev/9router/src/app/api/v1/search/route.js` → `src/sse/handlers/search.js` → `open-sse/handlers/search/index.js`  
**Estimated effort:** High — 10 dedicated search provider adapters + 6 chat-based search adapters + response normalizers + failover logic.

---

## What This Does

Adds a unified web search endpoint to the FastAPI proxy. Clients send a
provider ID + query, 9Router routes to the appropriate search API (dedicated
or chat-based), normalizes the response, and returns unified search results.

```
Client → POST /v1/search { model: "tavily", query: "latest AI news" }
           ↓
       resolve provider → "tavily" (dedicated search API)
           ↓
       build provider-specific request (URL, headers, body)
           ↓
       POST https://api.tavily.com/search { query, max_results, topic }
           ↓
       normalize response → unified SearchResult format
           ↓
       return { provider, query, results: [...], metrics: {...} }
```

---

## Key Characteristics

1. **Provider IS the model** — unlike chat/embeddings where model is
   `{alias}/{model_id}`, search uses provider as the model directly.
   `body.model` or `body.provider` identifies the search provider.

2. **Two search modes:**
   - **Dedicated search APIs** — providers with `searchConfig` (tavily, brave,
     serper, exa, perplexity, google-pse, linkup, searchapi, youcom, searxng)
   - **Chat-based LLM search** — providers with `searchViaChat` that use chat
     completions with built-in web search (gemini, openai, xai, kimi, minimax)

3. **10 dedicated providers** — each has its own request builder (URL, method,
   headers, body format) and response normalizer.

4. **6 chat-based providers** — each wraps chat completions differently
   (Gemini uses `google_search` tool, OpenAI uses `web_search_preview` tool,
   xAI uses `search_parameters`, etc.)

5. **Failover** — if a dedicated search fails with a retriable error, the
   system falls back to chat-based search if the provider supports both.

6. **Unified response format** — all providers normalize to:
   ```json
   {
     "provider": "tavily",
     "query": "latest AI news",
     "results": [{ "title", "url", "snippet", "position", ... }],
     "answer": null,
     "usage": { "queries_used": 1, "search_cost_usd": 0.008 },
     "metrics": { "response_time_ms": 450 }
   }
   ```

---

## Supported Providers

### Dedicated Search APIs (have `searchConfig`)

| Provider       | Upstream URL                                         | Method | Auth Header              | Body Format                                      | Response Shape                     |
|---------------|-----------------------------------------------------|--------|--------------------------|--------------------------------------------------|-------------------------------------|
| tavily        | https://api.tavily.com/search                       | POST   | Bearer                   | `{ query, max_results, topic, include_domains }` | `{ results: [{ title, url, content, score }] }` |
| brave-search  | https://api.search.brave.com/res/v1/web/search      | GET    | X-Subscription-Token     | Query params: `q, count, country, search_lang`   | `{ web: { results: [{ title, url, description }] } }` |
| serper        | https://google.serper.dev/search                    | POST   | X-API-Key                | `{ q, num, gl, hl }`                             | `{ organic: [{ title, link, snippet }] }` |
| exa           | https://api.exa.ai/search                           | POST   | x-api-key                | `{ query, numResults, type, text, highlights }`  | `{ results: [{ title, url, highlights, score }] }` |
| perplexity    | https://api.perplexity.ai/search                    | POST   | Bearer                   | `{ query, max_results, country }`                | `{ results: [{ title, url, snippet }] }` |
| google-pse    | https://www.googleapis.com/customsearch/v1          | GET    | (query param `key`)      | Query params: `key, cx, q, num`                  | `{ items: [{ title, link, snippet }] }` |
| linkup        | https://api.linkup.so/v1/search                     | POST   | Bearer                   | `{ q, depth, outputType, maxResults }`           | `{ results: [{ name, url, content }] }` |
| searchapi     | https://www.searchapi.io/api/v1/search              | GET    | (query param `api_key`)  | Query params: `engine, q, api_key`               | `{ organic_results: [{ title, link, snippet }] }` |
| youcom        | https://ydc-index.io/v1/search                      | GET    | X-API-Key                | Query params: `query, count`                     | `{ results: { web: [{ title, url, snippets }] } }` |
| searxng       | http://localhost:8888/search                        | GET    | None (noAuth)            | Query params: `q, format, categories`            | `{ results: [{ title, url, content }] }` |

### Chat-Based Search (have `searchViaChat`)

| Provider  | Chat Endpoint                               | Default Model        | Web Search Mechanism                          |
|----------|---------------------------------------------|----------------------|-----------------------------------------------|
| gemini   | generateContent with `google_search` tool   | gemini-2.5-flash     | `tools: [{ google_search: {} }]`              |
| openai   | /v1/chat/completions with `web_search` tool | gpt-4o-mini          | `tools: [{ type: "web_search_preview" }]`     |
| xai      | /v1/chat/completions with search params     | grok-4.20-reasoning  | `search_parameters: { mode: "auto" }`         |
| kimi     | Kimi chat API with web search               | kimi-k2.5            | Built-in web search in chat                   |
| minimax  | MiniMax chat API with web search            | MiniMax-M2.7         | Built-in web search in chat                   |

---

## Request / Response Format

**Request:**
```json
POST /v1/search
Authorization: Bearer <jwt_or_api_key>
Content-Type: application/json

{
  "model": "tavily",
  "query": "latest AI news",
  "max_results": 5,
  "search_type": "web",
  "country": "us",
  "language": "en",
  "time_range": "week",
  "offset": 0,
  "domain_filter": ["arxiv.org", "-reddit.com"],
  "content_options": {
    "full_page": true,
    "format": "markdown"
  },
  "provider_options": {
    "depth": "standard"
  }
}
```

- `model` or `provider` (required) — provider alias or ID
- `query` (required) — search query string
- `max_results` (optional) — max results to return (default: 5)
- `search_type` (optional) — `web` (default) or `news`
- `country` (optional) — ISO 3166-1 alpha-2 country code
- `language` (optional) — ISO 639-1 language code
- `time_range` (optional) — `day`, `week`, `month`, `year`, `any`
- `offset` (optional) — pagination offset
- `domain_filter` (optional) — include/exclude domains (prefix with `-` to exclude)
- `content_options` (optional) — full page content options
- `provider_options` (optional) — provider-specific options

**Response (unified format):**
```json
{
  "provider": "tavily",
  "query": "latest AI news",
  "results": [
    {
      "title": "AI News Today",
      "url": "https://example.com/ai-news",
      "display_url": "example.com/ai-news",
      "snippet": "Latest developments in artificial intelligence...",
      "position": 1,
      "score": 0.95,
      "published_at": "2026-05-23",
      "favicon_url": null,
      "content": {
        "format": "text",
        "text": "Full page content...",
        "length": 5000
      },
      "metadata": {
        "author": null,
        "language": "en",
        "source_type": null,
        "image_url": null
      },
      "citation": {
        "provider": "tavily",
        "retrieved_at": "2026-05-23T10:00:00Z",
        "rank": 1
      }
    }
  ],
  "answer": null,
  "usage": {
    "queries_used": 1,
    "search_cost_usd": 0.008
  },
  "metrics": {
    "response_time_ms": 450,
    "upstream_latency_ms": 420,
    "total_results_available": 100
  },
  "errors": []
}
```

---

## Phase 1 — Backend: Search Request Builders

**New file:** `backend/app/services/search_callers.py`

One builder function per dedicated search provider. Each returns
`(url, method, headers, body_or_params)`.

### 1.1 Tavily

```python
def build_tavily_request(params: dict, token: str) -> tuple[str, str, dict, dict]:
    """Build Tavily search request."""
    body = {
        "query": params["query"],
        "max_results": params.get("max_results", 5),
        "topic": "news" if params.get("search_type") == "news" else "general",
    }
    includes, excludes = parse_domain_filter(params.get("domain_filter"))
    if includes:
        body["include_domains"] = includes
    if excludes:
        body["exclude_domains"] = excludes
    if params.get("country"):
        body["country"] = params["country"]
    
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    return url, "POST", headers, body
```

### 1.2 Brave Search

```python
def build_brave_request(params: dict, token: str) -> tuple[str, str, dict, None]:
    """Build Brave Search request (GET with query params)."""
    endpoint = "/news/search" if params.get("search_type") == "news" else "/web/search"
    qp = {"q": params["query"], "count": str(params.get("max_results", 5))}
    if params.get("country"):
        qp["country"] = params["country"]
    if params.get("language"):
        qp["search_lang"] = params["language"]
    
    url = f"https://api.search.brave.com/res/v1{endpoint}?{urlencode(qp)}"
    headers = {"Accept": "application/json", "X-Subscription-Token": token}
    return url, "GET", headers, None
```

### 1.3 Serper

```python
def build_serper_request(params: dict, token: str) -> tuple[str, str, dict, dict]:
    """Build Serper search request."""
    endpoint = "/news" if params.get("search_type") == "news" else "/search"
    body = {"q": params["query"], "num": params.get("max_results", 5)}
    if params.get("country"):
        body["gl"] = params["country"].lower()
    if params.get("language"):
        body["hl"] = params["language"]
    
    url = f"https://google.serper.dev{endpoint}"
    headers = {"Content-Type": "application/json", "X-API-Key": token}
    return url, "POST", headers, body
```

### 1.4 Exa

```python
def build_exa_request(params: dict, token: str) -> tuple[str, str, dict, dict]:
    """Build Exa search request."""
    includes, excludes = parse_domain_filter(params.get("domain_filter"))
    body = {
        "query": params["query"],
        "numResults": params.get("max_results", 5),
        "type": "auto",
        "text": True,
        "highlights": True,
    }
    if includes:
        body["includeDomains"] = includes
    if excludes:
        body["excludeDomains"] = excludes
    if params.get("search_type") == "news":
        body["category"] = "news"
    
    url = "https://api.exa.ai/search"
    headers = {"Content-Type": "application/json", "x-api-key": token}
    return url, "POST", headers, body
```

### 1.5 Perplexity

```python
def build_perplexity_request(params: dict, token: str) -> tuple[str, str, dict, dict]:
    """Build Perplexity search request."""
    body = {"query": params["query"], "max_results": params.get("max_results", 5)}
    if params.get("country"):
        body["country"] = params["country"]
    if params.get("language"):
        body["search_language_filter"] = [params["language"]]
    if params.get("domain_filter"):
        body["search_domain_filter"] = params["domain_filter"]
    
    url = "https://api.perplexity.ai/search"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    return url, "POST", headers, body
```

### 1.6 Google PSE

```python
def build_google_pse_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, None]:
    """Build Google Programmable Search Engine request."""
    cx = provider_data.get("cx") or params.get("provider_options", {}).get("cx")
    if not cx:
        raise ValueError("Google PSE requires 'cx' (search engine ID) in providerSpecificData or provider_options")
    
    qp = {"key": token, "cx": cx, "q": params["query"], "num": str(min(params.get("max_results", 5), 10))}
    if params.get("country"):
        qp["gl"] = params["country"].lower()
    if params.get("language"):
        qp["hl"] = params["language"]
    
    time_range = params.get("time_range")
    if time_range and time_range != "any":
        date_map = {"day": "d1", "week": "w1", "month": "m1", "year": "y1"}
        if time_range in date_map:
            qp["dateRestrict"] = date_map[time_range]
    
    url = f"https://www.googleapis.com/customsearch/v1?{urlencode(qp)}"
    headers = {"Accept": "application/json"}
    return url, "GET", headers, None
```

### 1.7 — 1.10 Linkup, SearchAPI, You.com, SearXNG

Similar pattern — each builds URL + headers + body per their API spec.
Full implementations in `search_callers.py`.

### 1.11 Shared Utilities

```python
from urllib.parse import urlencode

def parse_domain_filter(domain_filter: list[str] | None) -> tuple[list[str], list[str]]:
    """Split domain filter into includes/excludes (excludes prefixed with '-')."""
    if not domain_filter:
        return [], []
    includes = [d for d in domain_filter if not d.startswith("-")]
    excludes = [d[1:] for d in domain_filter if d.startswith("-")]
    return includes, excludes

def to_page_number(offset: int | None, max_results: int) -> int | None:
    """Convert offset+maxResults to 1-indexed page number."""
    if not offset or offset <= 0 or max_results <= 0:
        return None
    return (offset // max_results) + 1
```

### 1.12 Dispatch Table

```python
SEARCH_BUILDERS = {
    "tavily": build_tavily_request,
    "brave-search": build_brave_request,
    "serper": build_serper_request,
    "exa": build_exa_request,
    "perplexity": build_perplexity_request,
    "google-pse": build_google_pse_request,
    "linkup": build_linkup_request,
    "searchapi": build_searchapi_request,
    "youcom": build_youcom_request,
    "searxng": build_searxng_request,
}
```

---

## Phase 2 — Backend: Response Normalizers

**New file:** `backend/app/services/search_normalizers.py`

One normalizer per provider. Each converts provider-specific response to
the unified `SearchResult` shape.

### 2.1 Unified SearchResult Shape

```python
from datetime import datetime

def make_result(provider_id: str, item: dict, idx: int) -> dict:
    """Build a unified SearchResult object."""
    url = item.get("url", "")
    return {
        "title": item.get("title", ""),
        "url": url,
        "display_url": url.replace("https://", "").replace("http://", "").split("?")[0] if url else None,
        "snippet": item.get("snippet", ""),
        "position": idx + 1,
        "score": min(1.0, max(0.0, item["score"])) if isinstance(item.get("score"), (int, float)) else None,
        "published_at": item.get("published_at"),
        "favicon_url": item.get("favicon_url"),
        "content": (
            {"format": item.get("text_format", "text"), "text": item["full_text"], "len(item['full_text'])}
            if item.get("full_text") else None
        ),
        "metadata": {
            "author": item.get("author"),
            "language": None,
            "source_type": item.get("source_type"),
            "image_url": item.get("image_url"),
        },
        "citation": {
            "provider": provider_id,
            "retrieved_at": datetime.utcnow().isoformat() + "Z",
            "rank": idx + 1,
        },
    }
```

### 2.2 Provider Normalizers

```python
def normalize_tavily(data: dict, query: str, search_type: str) -> dict:
    items = data.get("results", [])
    results = [
        make_result("tavily", {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": r.get("content", ""),
            "score": r.get("score"),
            "published_at": r.get("published_date"),
            "full_text": r.get("raw_content"),
            "text_format": "text",
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}

def normalize_brave(data: dict, query: str, search_type: str) -> dict:
    container = data.get("news" if search_type == "news" else "web", data)
    items = container.get("results", [])
    results = [
        make_result("brave-search", {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": r.get("description"),
            "published_at": r.get("page_age") or r.get("age"),
            "favicon_url": (r.get("meta_url") or {}).get("favicon"),
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": container.get("totalCount")}

# ... one normalizer per provider (serper, exa, perplexity, google-pse, linkup, searchapi, youcom, searxng)
```

### 2.3 Dispatch Table

```python
SEARCH_NORMALIZERS = {
    "tavily": normalize_tavily,
    "brave-search": normalize_brave,
    "serper": normalize_serper,
    "exa": normalize_exa,
    "perplexity": normalize_perplexity,
    "google-pse": normalize_google_pse,
    "linkup": normalize_linkup,
    "searchapi": normalize_searchapi,
    "youcom": normalize_youcom,
    "searxng": normalize_searxng,
}
```

---

## Phase 3 — Backend: Chat-Based Search Adapters

**New file:** `backend/app/services/search_chat.py`

For providers with `searchViaChat` (gemini, openai, xai, kimi, minimax),
wrap chat completions with web search tools into the unified search format.

### 3.1 Gemini Chat Search

```python
async def chat_search_gemini(client, api_key, query, max_results=10):
    """Gemini search via generateContent with google_search tool."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    body = {
        "contents": [{"role": "user", "parts": [{"text": query}]}],
        "tools": [{"google_search": {}}],
    }
    resp = await client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()
    
    candidate = data.get("candidates", [{}])[0]
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if "text" in p)
    
    # Extract citations from grounding metadata
    chunks = candidate.get("groundingMetadata", {}).get("groundingChunks", [])
    citations = [
        {"url": w.get("uri") or w.get("url", ""), "title": w.get("title", "")}
        for ch in chunks if (w := ch.get("web")) and (w.get("uri") or w.get("url"))
    ]
    
    tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
    return {"text": text, "citations": citations, "tokens": tokens}
```

### 3.2 OpenAI Chat Search

```python
async def chat_search_openai(client, api_key, query, max_results=10):
    """OpenAI search via chat completions with web_search_preview tool."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": query}],
        "tools": [{"type": "web_search_preview"}],
    }
    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    # Extract text and citations from tool call results
    choices = data.get("choices", [])
    text = choices[0].get("message", {}).get("content", "") if choices else ""
    citations = []  # Extract from tool call annotations if present
    
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return {"text": text, "citations": citations, "tokens": tokens}
```

### 3.3 xAI Chat Search

```python
async def chat_search_xai(client, api_key, query, max_results=10):
    """xAI search via chat completions with search_parameters."""
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "grok-3",
        "messages": [{"role": "user", "content": query}],
        "search_parameters": {"mode": "auto", "max_results": max_results},
        "return_citations": True,
    }
    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations = data.get("citations", [])
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return {"text": text, "citations": citations, "tokens": tokens}
```

### 3.4 Chat Search → Unified Result Converter

```python
def chat_result_to_search(provider_id: str, chat_result: dict, query: str) -> dict:
    """Convert chat-based search result to unified search format."""
    citations = chat_result.get("citations", [])
    results = [
        make_result(provider_id, {
            "title": c.get("title", ""),
            "url": c.get("url", ""),
            "snippet": c.get("snippet", ""),
        }, i) for i, c in enumerate(citations) if c.get("url")
    ]
    
    return {
        "provider": provider_id,
        "query": query,
        "results": results,
        "answer": chat_result.get("text"),
        "usage": {"queries_used": 1, "search_cost_usd": 0},
        "metrics": {"response_time_ms": 0, "total_results_available": len(results)},
        "errors": [],
    }
```

### 3.5 Chat Search Dispatch

```python
CHAT_SEARCH_ADAPTERS = {
    "gemini": chat_search_gemini,
    "openai": chat_search_openai,
    "xai": chat_search_xai,
    "kimi": chat_search_kimi,
    "minimax": chat_search_minimax,
}
```

---

## Phase 4 — Backend: Add `/v1/search` Route

**File:** `backend/app/routers/v1_proxy.py`

```python
@router.post("/search")
async def search(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """Unified web search proxy."""
    from app.services.search_callers import SEARCH_BUILDERS, parse_domain_filter
    from app.services.search_normalizers import SEARCH_NORMALIZERS
    from app.services.search_chat import CHAT_SEARCH_ADAPTERS, chat_result_to_search
    
    import time
    start_time = time.time()
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    # Accept provider or model field
    provider_input = body.get("provider") or body.get("model")
    query = body.get("query")
    
    if not provider_input:
        raise HTTPException(status_code=400, detail="Missing required field: provider (or model)")
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Missing required field: query")
    
    # Sanitize query
    query = query.strip()
    
    # Resolve provider
    provider_id = _resolve_provider_alias(provider_input)
    
    # Get provider info
    from app.routers.providers.constants import PROVIDER_DEFAULTS
    provider_defaults = PROVIDER_DEFAULTS.get(provider_id, {})
    
    # DB lookup for credentials
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.provider == provider_id, ProviderConnection.is_active == True)
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()
    
    if not connections and provider_id != "searxng":
        raise HTTPException(status_code=503, detail=f"No connection for provider: {provider_id}")
    
    # Extract search params
    search_params = {
        "query": query,
        "max_results": body.get("max_results", 5),
        "search_type": body.get("search_type", "web"),
        "country": body.get("country"),
        "language": body.get("language"),
        "time_range": body.get("time_range"),
        "offset": body.get("offset"),
        "domain_filter": body.get("domain_filter"),
        "content_options": body.get("content_options"),
        "provider_options": body.get("provider_options"),
    }
    
    # Route: dedicated search API first, then chat-based fallback
    last_error = None
    
    # Try dedicated search
    if provider_id in SEARCH_BUILDERS:
        builder = SEARCH_BUILDERS[provider_id]
        normalizer = SEARCH_NORMALIZERS.get(provider_id)
        
        for conn in (connections or [None]):
            data = json.loads(conn.data) if conn and conn.data else {}
            api_key = data.get("apiKey", "")
            provider_data = data
            
            try:
                url, method, headers, req_body = builder(search_params, api_key, provider_data)
                
                async with httpx.AsyncClient(timeout=15.0) as client:
                    if method == "GET":
                        resp = await client.get(url, headers=headers)
                    else:
                        resp = await client.post(url, headers=headers, json=req_body)
                    
                    resp.raise_for_status()
                    upstream_data = resp.json()
                
                # Normalize
                if normalizer:
                    normalized = normalizer(upstream_data, query, search_params["search_type"])
                else:
                    normalized = {"results": [], "totalResults": None}
                
                elapsed = int((time.time() - start_time) * 1000)
                return JSONResponse(content={
                    "provider": provider_id,
                    "query": query,
                    "results": normalized["results"][:search_params["max_results"]],
                    "answer": None,
                    "usage": {"queries_used": 1, "search_cost_usd": 0},
                    "metrics": {
                        "response_time_ms": elapsed,
                        "upstream_latency_ms": elapsed,
                        "total_results_available": normalized.get("totalResults"),
                    },
                    "errors": [],
                })
            
            except httpx.HTTPStatusError as e:
                last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
                if e.response.status_code < 500:
                    return JSONResponse(status_code=e.response.status_code, content={"error": {"message": e.response.text[:500]}})
                continue
            except Exception as e:
                last_error = {"status": 500, "detail": str(e)}
                continue
    
    # Fallback: chat-based search
    if provider_id in CHAT_SEARCH_ADAPTERS:
        chat_adapter = CHAT_SEARCH_ADAPTERS[provider_id]
        
        for conn in (connections or [None]):
            data = json.loads(conn.data) if conn and conn.data else {}
            api_key = data.get("apiKey", "")
            
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    chat_result = await chat_adapter(client, api_key, query, search_params["max_results"])
                
                elapsed = int((time.time() - start_time) * 1000)
                result_data = chat_result_to_search(provider_id, chat_result, query)
                result_data["metrics"]["response_time_ms"] = elapsed
                return JSONResponse(content=result_data)
            
            except Exception as e:
                last_error = {"status": 500, "detail": str(e)}
                continue
    
    error_msg = last_error.get("detail", "Search failed") if last_error else f"Provider '{provider_id}' does not support web search"
    error_status = last_error.get("status", 502) if last_error else 400
    return JSONResponse(status_code=error_status, content={"error": {"message": error_msg}})
```

---

## Phase 5 — Frontend: No Changes Required

The `/v1/search` endpoint is a pure API endpoint. No UI changes needed.
MediaProvidersPage already shows web search providers.

---

## Phase 6 — Testing

### 6.1 Manual curl tests

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — Tavily (dedicated, happy path):**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tavily", "query": "FastAPI Python tutorial", "max_results": 3}' \
  | jq '{provider, query, results_count: (.results | length), first_title: .results[0].title}'
```
Expected: `results_count: 3`, real search results.

**Test 2 — Brave Search:**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "brave", "query": "latest AI news", "max_results": 5}' \
  | jq '{provider, results_count: (.results | length)}'
```

**Test 3 — Serper:**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "serper", "query": "Python async programming", "country": "us"}' \
  | jq '{provider, results_count: (.results | length)}'
```

**Test 4 — Gemini chat-based search:**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini", "query": "what is the capital of France?"}' \
  | jq '{provider, answer: (.answer | .[0:100]), results_count: (.results | length)}'
```
Expected: `answer` contains text about Paris.

**Test 5 — SearXNG (noAuth, local):**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "searxng", "query": "open source AI models"}' \
  | jq '{provider, results_count: (.results | length)}'
```

**Test 6 — Missing query (400):**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tavily"}' | jq .
```
Expected: `400` with `"Missing required field: query"`.

**Test 7 — No connection (503):**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "nonexistent", "query": "test"}' | jq .
```
Expected: `503` or `400`.

**Test 8 — Domain filter:**
```bash
curl -s -X POST http://localhost:9000/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "tavily", "query": "machine learning", "domain_filter": ["arxiv.org", "-reddit.com"]}' \
  | jq '{results_count: (.results | length), urls: [.results[].url]}'
```

### 6.2 Regression check

```bash
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```

---

## Phase 7 — Report

1. **`docs/porting-status.md`** — Move `POST /v1/search` to "Fully Ported".
2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 6 as ✅.
3. **`docs/plans/v1-search.md`** (this file) — Update status to `Done`.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Google PSE requires `cx` | Must be configured in providerSpecificData. No default. |
| SearXNG requires local server | Runs on localhost:8888. Won't work in Docker unless port exposed. |
| Chat-based search returns `answer` field | Dedicated search returns `answer: null`. Clients should check both. |
| Failover logic | If dedicated search fails with 5xx, falls back to chat-based if provider supports both (e.g., perplexity has both searchConfig and searchViaChat). |
| Global timeout | 15 seconds per provider. Long queries may timeout. |
| Cost tracking | `search_cost_usd` is always 0 in Phase 1. Can be populated from `searchConfig.costPerQuery` later. |
| Citation extraction from chat | Chat-based search citations depend on each provider's response format. Gemini uses groundingMetadata, OpenAI uses tool call annotations, xAI uses citations array. |
| Combo expansion | The original supports combo expansion for search. Not implemented in Phase 1. |
| Content options | `full_page` and `format` options only supported by you.com. Other providers ignore them. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/search_callers.py` | NEW — 10 dedicated search request builders |
| `backend/app/services/search_normalizers.py` | NEW — 10 response normalizers |
| `backend/app/services/search_chat.py` | NEW — 6 chat-based search adapters |
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/search` handler |
| `docs/porting-status.md` | Move search endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 6 done |
| `docs/plans/v1-search.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Route handler | Medium | Provider dispatch, credential lookup, failover |
| Dedicated request builders (10) | Medium | Each is straightforward but different API |
| Response normalizers (10) | Medium | Map provider-specific response to unified shape |
| Chat-based adapters (6) | High | Each wraps chat completions differently, citation extraction varies |
| Failover logic | Medium | Dedicated → chat-based fallback on retriable errors |
| Query sanitization | Low | Strip control chars, normalize whitespace |
| Domain filter parsing | Low | Split includes/excludes |

**Overall:** High complexity — the most adapter-heavy endpoint alongside images.
10 dedicated providers + 6 chat-based providers = 16 adapters total. The
normalization layer adds another 10 functions. But each individual adapter is
relatively simple (HTTP request builder + response mapper).

**Recommended implementation order:**
1. Tavily (most popular, well-documented API)
2. Serper (simple POST, clean response)
3. Brave Search (GET with query params)
4. Exa (POST, similar to Tavily)
5. SearXNG (noAuth, local)
6. Perplexity, Google PSE, Linkup, SearchAPI, You.com
7. Chat-based: Gemini (most complex, groundingMetadata)
8. Chat-based: OpenAI, xAI, Kimi, MiniMax
