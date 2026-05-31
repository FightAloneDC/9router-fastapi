"""Xiaomi MiMo model fetching.

Fetches available models from Xiaomi MiMo API.
"""

import httpx

from app.providers.xiaomi_mimo.config import XiaomiMimoConfig
from app.utils.url import url_path_join

_config = XiaomiMimoConfig()

MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")
AUTH_HEADER = _config.AUTH_HEADER
AUTH_PREFIX = _config.AUTH_PREFIX
TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    """Extract models list from Xiaomi MiMo API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Xiaomi MiMo.

    Args:
        api_key: Xiaomi MiMo API key.

    Returns:
        List of raw model dicts from API.

    Raises:
        httpx.HTTPStatusError: If API returns non-success status.
        httpx.ConnectError: If cannot connect to Xiaomi MiMo.
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
