"""Tortoise TTS model fetching — local, no standard listing."""

from app.providers.tortoise.config import TortoiseConfig

_config: TortoiseConfig = TortoiseConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """Tortoise TTS does not expose a standard model listing endpoint."""
    return []
