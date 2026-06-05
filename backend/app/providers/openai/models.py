"""OpenAI model fetching — uses shared helper."""

from app.providers.openai.config import OpenaiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: OpenaiConfig = OpenaiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from OpenAI API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from OpenAI."""
    return await fetch_models_header_auth(_config, api_key)
