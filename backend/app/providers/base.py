"""Pydantic base model for provider model fetch configuration."""

from typing import Optional

from pydantic import BaseModel, Field


class ProviderModelFetchConfig(BaseModel):
    """Configuration for fetching available models from a provider API."""

    url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    authHeader: Optional[str] = None
    authPrefix: Optional[str] = None
    authQuery: Optional[str] = None
    responseKey: str = "data"

    model_config = {"frozen": True}

    def parseResponse(self, data: dict) -> list:
        """Extract models list from the API response data."""
        return data.get(self.responseKey, [])
