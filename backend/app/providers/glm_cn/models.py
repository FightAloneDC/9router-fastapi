"""GLM (China) model fetching — uses shared helper."""

from app.providers.glm_cn.config import GlmCnConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: GlmCnConfig = GlmCnConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from GLM (China) API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from GLM (China)."""
    return await fetch_models_header_auth(_config, api_key)
