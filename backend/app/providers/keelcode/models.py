"""Keelcode model fetching — GET /v1/models with Bearer."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.keelcode.config import KeelcodeConfig
from app.utils.url import url_path_join

_config: KeelcodeConfig = KeelcodeConfig()
TIMEOUT: float = 15.0


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Keelcode API response."""
    items = data.get("data", data if isinstance(data, list) else [])
    if not isinstance(items, list):
        return []
    result: list[dict] = []
    for m in items:
        if isinstance(m, str):
            result.append(
                {"id": m, "name": m, "type": "llm"}
            )
            continue
        if not isinstance(m, dict):
            continue
        model_id = m.get("id") or m.get("name")
        if not model_id:
            continue
        result.append(
            {
                "id": model_id,
                "name": m.get("name", model_id),
                "type": "llm",
            }
        )
    return result


async def fetch_models(
    api_key: str,
    data: dict | None = None,
) -> list[dict]:
    """Fetch available models from Keelcode."""
    if not api_key:
        raise ValueError("No access token configured")

    base_url = _config.BASE_URL
    if data and data.get("baseUrl"):
        base_url = str(data["baseUrl"]).rstrip("/")
        if base_url.endswith("/messages"):
            base_url = base_url[: -len("/messages")]

    url: str = url_path_join(base_url, "models")
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        f"{_config.AUTH_HEADER}": (
            f"{_config.AUTH_PREFIX}{api_key}"
        ),
    }
    if _config.EXTRA_HEADERS:
        headers.update(_config.EXTRA_HEADERS)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp: httpx.Response = await client.get(
            url, headers=headers
        )
        resp.raise_for_status()
        body: Any = resp.json()
        if not isinstance(body, dict):
            body = {"data": body}
        return parse_response(body)
