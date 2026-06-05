"""Provider class — unified accessor for per-provider config and models.

Usage:
    from app.providers import PROVIDER_CEREBRAS
    from app.providers.provider import Provider

    p = Provider(PROVIDER_CEREBRAS)
    p.config()            # CerebrasConfig instance
    p.metadata()          # CerebrasMetadata instance
    p.base_url()          # "https://api.cerebras.ai/v1"
    p.alias()             # "cb"
    p.parse_response({})  # []
    await p.fetch_models(api_key)
"""

import importlib

from app.providers.base import BaseMetadata, BaseProviderConfig


class Provider:
    """Unified accessor for provider config and models."""

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._module_name: str = name.replace("-", "_")
        self._config: BaseProviderConfig | None = None
        self._metadata: BaseMetadata | None = None
        self._models = None

    def _load_config(self) -> BaseProviderConfig:
        if self._config is None:
            module = importlib.import_module(
                f"app.providers.{self._module_name}.config"
            )
            for attr in dir(module):
                if attr.endswith("Config") and attr != "BaseProviderConfig":
                    cls = getattr(module, attr)
                    if isinstance(cls, type) and issubclass(cls, BaseProviderConfig):
                        self._config = cls()
                        return self._config
            raise ValueError(
                f"No Config class found in app.providers.{self._module_name}.config"
            )
        return self._config

    def _load_metadata(self) -> BaseMetadata:
        if self._metadata is None:
            module = importlib.import_module(
                f"app.providers.{self._module_name}.config"
            )
            for attr in dir(module):
                if attr.endswith("Metadata") and attr != "BaseMetadata":
                    cls = getattr(module, attr)
                    if isinstance(cls, type) and issubclass(cls, BaseMetadata):
                        self._metadata = cls()
                        return self._metadata
            raise ValueError(
                f"No Metadata class found in app.providers.{self._module_name}.config"
            )
        return self._metadata

    def _load_models(self):
        if self._models is None:
            self._models = importlib.import_module(
                f"app.providers.{self._module_name}.models"
            )
        return self._models

    def config(self) -> BaseProviderConfig:
        """Return the provider's config instance."""
        return self._load_config()

    def metadata(self) -> BaseMetadata:
        """Return the provider's UI metadata instance."""
        return self._load_metadata()

    def base_url(self) -> str:
        """Return provider base URL."""
        return self._load_config().BASE_URL

    def alias(self) -> str:
        """Return provider alias (e.g. 'cb', 'gq')."""
        return self._load_config().ALIAS

    def parse_response(self, data: dict) -> list:
        """Parse provider API response into model list."""
        return self._load_models().parse_response(data)

    async def fetch_models(self, api_key: str) -> list[dict]:
        """Fetch available models from provider API."""
        return await self._load_models().fetch_models(api_key)
