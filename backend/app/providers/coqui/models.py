"""Coqui TTS model fetching — no standard API listing."""

from app.providers.coqui.config import CoquiConfig

_config: CoquiConfig = CoquiConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """Coqui does not expose a standard model listing endpoint."""
    return []
