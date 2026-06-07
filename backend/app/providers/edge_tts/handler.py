"""Edge TTS handler — no authentication required."""

from app.providers.base import BaseProviderHandler, ValidateResult


class EdgeTtsHandler(BaseProviderHandler):
    """Handler for Edge TTS provider (no auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        return ValidateResult(valid=True, models=None)
