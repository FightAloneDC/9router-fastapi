"""Command Code model fetching — uses shared helper."""

from app.providers.commandcode.config import CommandcodeConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: CommandcodeConfig = CommandcodeConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Command Code API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Command Code."""
    return await fetch_models_header_auth(_config, api_key)
