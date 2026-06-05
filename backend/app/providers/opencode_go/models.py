"""OpenCode Go model fetching — uses shared helper."""

from app.providers.opencode_go.config import OpencodeGoConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: OpencodeGoConfig = OpencodeGoConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from OpenCode Go API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from OpenCode Go."""
    return await fetch_models_header_auth(_config, api_key)
