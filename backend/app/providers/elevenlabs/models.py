"""ElevenLabs model fetching.

Fetches available models from ElevenLabs API.
"""

import httpx

from app.providers.elevenlabs.config import ElevenlabsConfig
from app.utils.url import url_path_join

_config = ElevenlabsConfig()

MODEL_FETCH_URL = url_path_join(_config.BASE_URL, "models")
AUTH_HEADER = _config.AUTH_HEADER
AUTH_PREFIX = _config.AUTH_PREFIX
TIMEOUT = 15.0


def parse_response(data) -> list:
    """Extract models list from ElevenLabs API response.

    ElevenLabs returns a plain list of model objects.
    Normalize to include 'id' key from 'model_id'.
    """
    if isinstance(data, list):
        models = data
    else:
        models = data.get("data", [])
    for m in models:
        if isinstance(m, dict) and "id" not in m and "model_id" in m:
            m["id"] = m["model_id"]
    return models


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from ElevenLabs.

    Args:
        api_key: ElevenLabs API key.

    Returns:
        List of raw model dicts from API.

    Raises:
        httpx.HTTPStatusError: If API returns non-success status.
        httpx.ConnectError: If cannot connect to ElevenLabs.
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
