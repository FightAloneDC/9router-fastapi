"""Vertex Partner model fetching — uses shared helper."""

from app.providers.vertex_partner.config import VertexPartnerConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: VertexPartnerConfig = VertexPartnerConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Vertex Partner API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Vertex Partner."""
    return await fetch_models_header_auth(_config, api_key)
