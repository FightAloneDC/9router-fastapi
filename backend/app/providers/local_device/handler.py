"""Local Device handler — no authentication required."""

from app.providers.base import BaseProviderHandler, ValidateResult


class LocalDeviceHandler(BaseProviderHandler):
    """Handler for Local Device provider (no auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        return ValidateResult(valid=True, models=None)
