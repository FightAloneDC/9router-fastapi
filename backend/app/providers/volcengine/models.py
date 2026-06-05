"""Volcengine Ark model fetching — uses shared helper."""

from app.providers.volcengine.config import VolcengineConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: VolcengineConfig = VolcengineConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Volcengine Ark API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Volcengine Ark."""
    return await fetch_models_header_auth(_config, api_key)
