"""Jina Reader model fetching.

Fetches available models from Jina Reader API.
"""

import httpx

from app.providers.jina_reader.config import JinaReaderConfig
from app.utils.url import url_path_join

_config = JinaReaderConfig()

MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")
AUTH_HEADER = _config.AUTH_HEADER
AUTH_PREFIX = _config.AUTH_PREFIX
TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    """Extract models list from Jina Reader API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Jina Reader.

    Args:
        api_key: Jina Reader API key.

    Returns:
        List of raw model dicts from API.

    Raises:
        httpx.HTTPStatusError: If API returns non-success status.
        httpx.ConnectError: If cannot connect to Jina Reader.
        httpx.TimeoutException: If request times out.
    """
    headers = {
        "Content-Type": "application/json",
        AUTH_HEADER: f"{AUTH_PREFIX}{api_key}",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(MODEL_FETCH_URL, headers=headers)
        resp.raise_for_status()
        return parse_response(resp.json())
