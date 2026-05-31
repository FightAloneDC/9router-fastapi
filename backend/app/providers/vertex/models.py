"""Vertex AI model fetching.

Fetches available models from Vertex AI API.
"""

import httpx

from app.providers.vertex.config import VertexConfig
from app.utils.url import url_path_join

_config = VertexConfig()

MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")
AUTH_HEADER = _config.AUTH_HEADER
AUTH_PREFIX = _config.AUTH_PREFIX
TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    """Extract models list from Vertex AI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Vertex AI.

    Args:
        api_key: Vertex AI API key.

    Returns:
        List of raw model dicts from API.

    Raises:
        httpx.HTTPStatusError: If API returns non-success status.
        httpx.ConnectError: If cannot connect to Vertex AI.
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
