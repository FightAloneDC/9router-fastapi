"""POST /v1/web/fetch — Web page content fetching proxy."""

import json
import time

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.services.api_key_auth import validate_api_key
from app.services.usage_tracking import save_request_tracking
from app.models.provider import ProviderConnection
from app.routers.providers.constants import PROVIDER_DEFAULTS

router = APIRouter()

# Provider-specific fetch adapters
_FETCH_ADAPTERS: dict[str, dict[str, str | None | object]] = {
    "jina-reader": {
        "base_url": "https://r.jina.ai",
        "method": "GET",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "build_url": lambda base, url, fmt: f"{base}/{url}",
        "build_body": None,
    },
    "tavily": {
        "base_url": "https://api.tavily.com/extract",
        "method": "POST",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "build_url": lambda base, url, fmt: base,
        "build_body": lambda url, fmt: {"urls": [url], "format": fmt},
    },
    "exa": {
        "base_url": "https://api.exa.ai/contents",
        "method": "POST",
        "auth_header": "x-api-key",
        "auth_prefix": "",
        "build_url": lambda base, url, fmt: base,
        "build_body": lambda url, fmt: {"urls": [url], "text": True},
    },
    "firecrawl": {
        "base_url": "https://api.firecrawl.dev/v1/scrape",
        "method": "POST",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "build_url": lambda base, url, fmt: base,
        "build_body": lambda url, fmt: {"url": url, "formats": [fmt]},
    },
}


async def _resolve_webfetch_connection(
    provider: str | None, db: AsyncSession,
) -> tuple[str, str] | None:
    """Resolve a webFetch connection. Returns (provider_id, api_key) or None."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.is_active == True)
    )
    connections = result.scalars().all()

    if provider:
        for conn in connections:
            if conn.provider == provider:
                data: dict = json.loads(conn.data) if conn.data else {}
                api_key: str = data.get("apiKey", "")
                return (conn.provider, api_key)
        return None

    # Auto-detect: find first active webFetch provider
    for conn in connections:
        defaults: dict = PROVIDER_DEFAULTS.get(conn.provider, {})
        kinds: list[str] = defaults.get("serviceKinds", ["llm"])
        if "webFetch" in kinds:
            data: dict = json.loads(conn.data) if conn.data else {}
            api_key: str = data.get("apiKey", "")
            return (conn.provider, api_key)

    return None


@router.post("/web/fetch")
async def web_fetch(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """Fetch web page content via a configured webFetch provider.

    Request body:
        url (str): The URL to fetch.
        format (str): Output format — "markdown" (default), "text", or "html".
        provider (str, optional): Provider ID to use. Auto-detects if omitted.

    Returns:
        JSON with { success, url, content, format, provider }.
    """
    body: dict = await request.json()
    url: str = body.get("url", "")
    fmt: str = body.get("format", "markdown")
    requested_provider: str | None = body.get("provider")

    if not url:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "url is required"}},
        )

    resolved = await _resolve_webfetch_connection(requested_provider, db)
    if not resolved:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": f"No active webFetch provider found{f' for {requested_provider}' if requested_provider else ''}"}},
        )

    provider_id, api_key = resolved
    adapter = _FETCH_ADAPTERS.get(provider_id)
    if not adapter:
        return JSONResponse(
            status_code=501,
            content={"error": {"message": f"Provider {provider_id} does not have a web fetch adapter"}},
        )

    upstream_url: str = adapter["build_url"](adapter["base_url"], url, fmt)  # type: ignore[operator]
    headers: dict[str, str] = {}
    if api_key and adapter["auth_header"]:
        headers[adapter["auth_header"]] = f"{adapter['auth_prefix']}{api_key}"  # type: ignore[operator]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            request_start_time: float = time.time()
            if adapter["method"] == "GET":
                resp = await client.get(upstream_url, headers=headers, follow_redirects=True)
            else:
                body_data: dict = adapter["build_body"](url, fmt) if adapter["build_body"] else {}  # type: ignore[operator]
                headers["Content-Type"] = "application/json"
                resp = await client.post(upstream_url, headers=headers, json=body_data)
            total_latency_ms: int = int((time.time() - request_start_time) * 1000)

            if resp.status_code >= 400:
                return JSONResponse(
                    status_code=resp.status_code,
                    content={"error": {"message": f"{provider_id} returned {resp.status_code}: {resp.text[:300]}"}},
                )

            content: str = resp.text

            # Track usage (web fetch — no token counts)
            await save_request_tracking(
                db,
                provider=provider_id,
                model=provider_id,
                endpoint="/v1/web/fetch",
                latency_ttft=total_latency_ms,
                latency_total=total_latency_ms,
                request_body=body,
                provider_request_body={"url": url, "format": fmt, "provider": provider_id},
                provider_response_body={"content_length": len(content)},
                response_body={"success": True, "url": url, "content": content, "format": fmt, "provider": provider_id},
            )

            return JSONResponse(content={
                "success": True,
                "url": url,
                "content": content,
                "format": fmt,
                "provider": provider_id,
            })

        except httpx.ConnectError:
            return JSONResponse(
                status_code=502,
                content={"error": {"message": f"Cannot connect to {provider_id}"}},
            )
        except httpx.TimeoutException:
            return JSONResponse(
                status_code=504,
                content={"error": {"message": f"{provider_id} request timed out"}},
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": {"message": str(e)[:300]}},
            )
