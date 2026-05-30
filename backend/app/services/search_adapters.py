"""Search adapters for /v1/search endpoint.

Provides request builders and response normalizers for dedicated search APIs.
Each provider has a builder (returns url, method, headers, body) and a
normalizer (converts provider response to unified SearchResult format).

Supported providers:
  - tavily, brave-search, serper, exa, perplexity, google-pse,
    linkup, searchapi, youcom, searxng
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx


# ─────────────────────────────────────────────────────────────────────────────
# Shared utilities
# ─────────────────────────────────────────────────────────────────────────────


def parse_domain_filter(domain_filter: list[str] | None) -> tuple[list[str], list[str]]:
    """Split domain filter into includes/excludes (excludes prefixed with '-')."""
    if not domain_filter:
        return [], []
    includes = [d for d in domain_filter if not d.startswith("-")]
    excludes = [d[1:] for d in domain_filter if d.startswith("-")]
    return includes, excludes


def make_result(provider_id: str, item: dict, idx: int) -> dict:
    """Build a unified SearchResult object."""
    url = item.get("url", "")
    full_text = item.get("full_text")
    content_block = None
    if full_text:
        content_block = {
            "format": item.get("text_format", "text"),
            "text": full_text,
            "length": len(full_text),
        }

    return {
        "title": item.get("title", ""),
        "url": url,
        "display_url": url.replace("https://", "").replace("http://", "").split("?")[0] if url else None,
        "snippet": item.get("snippet", ""),
        "position": idx + 1,
        "score": min(1.0, max(0.0, item["score"])) if isinstance(item.get("score"), (int, float)) else None,
        "published_at": item.get("published_at"),
        "favicon_url": item.get("favicon_url"),
        "content": content_block,
        "metadata": {
            "author": item.get("author"),
            "language": None,
            "source_type": item.get("source_type"),
            "image_url": item.get("image_url"),
        },
        "citation": {
            "provider": provider_id,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "rank": idx + 1,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Request builders
# ─────────────────────────────────────────────────────────────────────────────


def build_tavily_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, dict]:
    """Build Tavily search request."""
    body: dict[str, Any] = {
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


def build_brave_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, None]:
    """Build Brave Search request (GET with query params)."""
    endpoint = "/news/search" if params.get("search_type") == "news" else "/web/search"
    qp: dict[str, str] = {"q": params["query"], "count": str(params.get("max_results", 5))}
    if params.get("country"):
        qp["country"] = params["country"]
    if params.get("language"):
        qp["search_lang"] = params["language"]

    url = f"https://api.search.brave.com/res/v1{endpoint}?{urlencode(qp)}"
    headers = {"Accept": "application/json", "X-Subscription-Token": token}
    return url, "GET", headers, None


def build_serper_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, dict]:
    """Build Serper search request."""
    endpoint = "/news" if params.get("search_type") == "news" else "/search"
    body: dict[str, Any] = {"q": params["query"], "num": params.get("max_results", 5)}
    if params.get("country"):
        body["gl"] = params["country"].lower()
    if params.get("language"):
        body["hl"] = params["language"]

    url = f"https://google.serper.dev{endpoint}"
    headers = {"Content-Type": "application/json", "X-API-Key": token}
    return url, "POST", headers, body


def build_exa_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, dict]:
    """Build Exa search request."""
    includes, excludes = parse_domain_filter(params.get("domain_filter"))
    body: dict[str, Any] = {
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


def build_perplexity_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, dict]:
    """Build Perplexity search request."""
    body: dict[str, Any] = {"query": params["query"], "max_results": params.get("max_results", 5)}
    if params.get("country"):
        body["country"] = params["country"]
    if params.get("language"):
        body["search_language_filter"] = [params["language"]]
    if params.get("domain_filter"):
        body["search_domain_filter"] = params["domain_filter"]

    url = "https://api.perplexity.ai/search"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    return url, "POST", headers, body


def build_google_pse_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, None]:
    """Build Google Programmable Search Engine request."""
    cx = provider_data.get("cx") or (params.get("provider_options") or {}).get("cx")
    if not cx:
        raise ValueError("Google PSE requires 'cx' (search engine ID) in providerSpecificData or provider_options")

    qp: dict[str, str] = {"key": token, "cx": cx, "q": params["query"], "num": str(min(params.get("max_results", 5), 10))}
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


def build_linkup_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, dict]:
    """Build Linkup search request."""
    body: dict[str, Any] = {
        "q": params["query"],
        "depth": (params.get("provider_options") or {}).get("depth", "standard"),
        "outputType": "searchResults",
        "maxResults": params.get("max_results", 5),
    }
    url = "https://api.linkup.so/v1/search"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    return url, "POST", headers, body


def build_searchapi_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, None]:
    """Build SearchAPI request (GET with query params)."""
    qp: dict[str, str] = {
        "engine": "google",
        "q": params["query"],
        "api_key": token,
        "num": str(params.get("max_results", 5)),
    }
    if params.get("country"):
        qp["gl"] = params["country"].lower()
    if params.get("language"):
        qp["hl"] = params["language"]

    url = f"https://www.searchapi.io/api/v1/search?{urlencode(qp)}"
    headers = {"Accept": "application/json"}
    return url, "GET", headers, None


def build_youcom_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, None]:
    """Build You.com search request (GET with query params)."""
    qp: dict[str, str] = {"query": params["query"], "count": str(params.get("max_results", 5))}
    url = f"https://api.you.com/v1/search?{urlencode(qp)}"
    headers = {"Accept": "application/json", "X-API-Key": token}
    return url, "GET", headers, None


def build_searxng_request(params: dict, token: str, provider_data: dict) -> tuple[str, str, dict, None]:
    """Build SearXNG search request (GET with query params, no auth)."""
    base_url = provider_data.get("baseUrl", "http://localhost:8888")
    qp: dict[str, str] = {
        "q": params["query"],
        "format": "json",
        "categories": "general",
    }
    url = f"{base_url.rstrip('/')}/search?{urlencode(qp)}"
    headers = {"Accept": "application/json"}
    return url, "GET", headers, None


# ─────────────────────────────────────────────────────────────────────────────
# Response normalizers
# ─────────────────────────────────────────────────────────────────────────────


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


def normalize_serper(data: dict, query: str, search_type: str) -> dict:
    items = data.get("organic", data.get("results", []))
    results = [
        make_result("serper", {
            "title": r.get("title"),
            "url": r.get("link") or r.get("url"),
            "snippet": r.get("snippet"),
            "position": r.get("position"),
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}


def normalize_exa(data: dict, query: str, search_type: str) -> dict:
    items = data.get("results", [])
    results = [
        make_result("exa", {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": (r.get("highlights") or [None])[0] if r.get("highlights") else None,
            "score": r.get("score"),
            "published_at": r.get("publishedDate"),
            "full_text": r.get("text"),
            "text_format": "text",
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}


def normalize_perplexity(data: dict, query: str, search_type: str) -> dict:
    items = data.get("results", [])
    results = [
        make_result("perplexity", {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": r.get("snippet"),
            "published_at": r.get("published_date"),
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}


def normalize_google_pse(data: dict, query: str, search_type: str) -> dict:
    items = data.get("items", [])
    results = [
        make_result("google-pse", {
            "title": r.get("title"),
            "url": r.get("link"),
            "snippet": r.get("snippet"),
            "image_url": (r.get("pagemap") or {}).get("cse_image", [{}])[0].get("src"),
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": data.get("searchInformation", {}).get("totalResults")}


def normalize_linkup(data: dict, query: str, search_type: str) -> dict:
    items = data.get("results", [])
    results = [
        make_result("linkup", {
            "title": r.get("name"),
            "url": r.get("url"),
            "snippet": r.get("content"),
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}


def normalize_searchapi(data: dict, query: str, search_type: str) -> dict:
    items = data.get("organic_results", [])
    results = [
        make_result("searchapi", {
            "title": r.get("title"),
            "url": r.get("link"),
            "snippet": r.get("snippet"),
            "position": r.get("position"),
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}


def normalize_youcom(data: dict, query: str, search_type: str) -> dict:
    hits = data.get("results", data.get("hits", {}))
    items = hits.get("web", hits) if isinstance(hits, dict) else hits
    if not isinstance(items, list):
        items = []
    results = [
        make_result("youcom", {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": (r.get("snippets") or [None])[0] if r.get("snippets") else None,
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}


def normalize_searxng(data: dict, query: str, search_type: str) -> dict:
    items = data.get("results", [])
    results = [
        make_result("searxng", {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": r.get("content"),
            "published_at": r.get("publishedDate"),
        }, i) for i, r in enumerate(items)
    ]
    return {"results": results, "totalResults": len(results)}


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch tables
# ─────────────────────────────────────────────────────────────────────────────

BuilderFn = Any  # (params, token, provider_data) -> (url, method, headers, body|None)
NormalizerFn = Any  # (data, query, search_type) -> dict

SEARCH_BUILDERS: dict[str, BuilderFn] = {
    "tavily": build_tavily_request,
    "brave-search": build_brave_request,
    "serper": build_serper_request,
    "exa": build_exa_request,
    "perplexity": build_perplexity_request,
    "google-pse": build_google_pse_request,
    "linkup": build_linkup_request,
    "searchapi": build_searchapi_request,
    "you-com": build_youcom_request,
    "searxng": build_searxng_request,
}

SEARCH_NORMALIZERS: dict[str, NormalizerFn] = {
    "tavily": normalize_tavily,
    "brave-search": normalize_brave,
    "serper": normalize_serper,
    "exa": normalize_exa,
    "perplexity": normalize_perplexity,
    "google-pse": normalize_google_pse,
    "linkup": normalize_linkup,
    "searchapi": normalize_searchapi,
    "you-com": normalize_youcom,
    "searxng": normalize_searxng,
}

# Providers that don't require an API key (local/self-hosted)
_NOAUTH_SEARCH_PROVIDERS = {"searxng"}


async def execute_search(
    client: httpx.AsyncClient,
    provider_id: str,
    params: dict,
    token: str,
    provider_data: dict | None = None,
) -> dict:
    """Execute a search request and return normalized results.

    Args:
        client: httpx async client
        provider_id: search provider ID
        params: normalized search params (query, max_results, etc.)
        token: API key/token
        provider_data: connection-specific data (baseUrl, cx, etc.)

    Returns:
        Unified search response dict.
    """
    if provider_data is None:
        provider_data = {}

    builder = SEARCH_BUILDERS.get(provider_id)
    normalizer = SEARCH_NORMALIZERS.get(provider_id)

    if not builder or not normalizer:
        raise ValueError(f"Unsupported search provider: {provider_id}")

    url, method, headers, body = builder(params, token, provider_data)

    if method == "GET":
        resp = await client.get(url, headers=headers)
    else:
        resp = await client.post(url, headers=headers, json=body)

    resp.raise_for_status()
    data = resp.json()

    normalized = normalizer(data, params["query"], params.get("search_type", "web"))

    return {
        "provider": provider_id,
        "query": params["query"],
        "results": normalized["results"],
        "answer": None,
        "usage": {"queries_used": 1},
        "metrics": {
            "total_results_available": normalized.get("totalResults"),
        },
        "errors": [],
    }
