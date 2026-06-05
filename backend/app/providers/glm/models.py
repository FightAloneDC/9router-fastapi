"""GLM Coding model fetching — uses shared helper."""

from app.providers.glm.config import GlmConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: GlmConfig = GlmConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from GLM Coding API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from GLM Coding."""
    return await fetch_models_header_auth(_config, api_key)
