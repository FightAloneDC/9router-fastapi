"""Local Device model fetching — no auth, local espeak."""

from app.providers.local_device.config import LocalDeviceConfig

_config: LocalDeviceConfig = LocalDeviceConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """Local Device voices are fetched via voice_fetchers, not model listing."""
    return []
