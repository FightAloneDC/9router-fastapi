"""Deepgram model fetching.

Fetches available models from Deepgram API.
"""

import httpx

from app.providers.deepgram.config import DeepgramConfig
from app.utils.url import url_path_join

_config = DeepgramConfig()

MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")
AUTH_HEADER = _config.AUTH_HEADER
AUTH_PREFIX = _config.AUTH_PREFIX
TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    """Extract models list from Deepgram API response.

    Deepgram returns {stt: [...], tts: [...], languages: [...]}.
    Combine stt and tts into a single list.
    Normalize to include 'id' key from 'canonical_name'.
    """
    models = []
    models.extend(data.get("stt", []))
    models.extend(data.get("tts", []))
    for m in models:
        if isinstance(m, dict) and "id" not in m:
            m["id"] = m.get("canonical_name") or m.get("name") or m.get("uuid", "")
    return models


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Deepgram.

    Args:
        api_key: Deepgram API key.

    Returns:
        List of raw model dicts from API.

    Raises:
        httpx.HTTPStatusError: If API returns non-success status.
        httpx.ConnectError: If cannot connect to Deepgram.
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
