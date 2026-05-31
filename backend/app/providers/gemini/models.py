"""Gemini model fetching.

Fetches available models from Gemini API using query parameter auth.
"""

import httpx

from app.providers.gemini.config import GeminiConfig
from app.utils.url import url_path_join

_config = GeminiConfig()

MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")
TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    """Extract models list from Gemini API response.

    Gemini returns {models: [{name: "models/gemini-2.5-flash", ...}]}.
    Normalize to include 'id' key from 'name'.
    """
    models = data.get("models", [])
    for m in models:
        if "id" not in m and "name" in m:
            m["id"] = m["name"]
    return models


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Gemini.

    Gemini uses query parameter auth (?key=API_KEY) instead of headers.

    Args:
        api_key: Gemini API key.

    Returns:
        List of raw model dicts from API.

    Raises:
        httpx.HTTPStatusError: If API returns non-success status.
        httpx.ConnectError: If cannot connect to Gemini.
        httpx.TimeoutException: If request times out.
    """
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(MODEL_FETCH_URL, headers=headers, params=params)
        resp.raise_for_status()
        return parse_response(resp.json())
