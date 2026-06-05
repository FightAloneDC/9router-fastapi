"""Vercel AI Gateway model fetching — uses shared helper."""

from app.providers.vercel_ai_gateway.config import VercelAiGatewayConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: VercelAiGatewayConfig = VercelAiGatewayConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Vercel AI Gateway API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Vercel AI Gateway."""
    return await fetch_models_header_auth(_config, api_key)
