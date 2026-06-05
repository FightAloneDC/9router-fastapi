"""DeepSeek model fetching — uses shared helper (OpenAI-compatible pattern)."""

from app.providers.deepseek.config import DeepseekConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: DeepseekConfig = DeepseekConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from DeepSeek API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from DeepSeek."""
    return await fetch_models_header_auth(_config, api_key)
