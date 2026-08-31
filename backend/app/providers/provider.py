"""Provider class — unified accessor for per-provider config and models.

Usage:
    ``Provider("cerebras")`` then ``config()``, ``metadata()``,
    ``base_url()``, ``alias()``, ``parse_response({})``,
    ``await fetch_models(api_key)``.
"""

import importlib

from app.providers.base import BaseMetadata, BaseProviderConfig, BaseProviderHandler


class Provider:
    """Unified accessor for provider config and models."""

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._module_name: str = name.replace("-", "_")
        self._config: BaseProviderConfig | None = None
        self._metadata: BaseMetadata | None = None
        self._models = None
        self._handler: BaseProviderHandler | None = None

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

    async def fetch_models(self, api_key: str, **kwargs) -> list[dict]:
        """Fetch available models from provider API."""
        return await self._load_models().fetch_models(api_key, **kwargs)

    def handler(self) -> BaseProviderHandler:
        """Return the provider's handler instance.

        Tries to load provider-specific handler class first.
        Falls back to BaseProviderHandler with provider config.
        """
        if self._handler is None:
            try:
                module = importlib.import_module(
                    f"app.providers.{self._module_name}.handler"
                )
                for attr in dir(module):
                    cls = getattr(module, attr)
                    if (
                        isinstance(cls, type)
                        and issubclass(cls, BaseProviderHandler)
                        and cls is not BaseProviderHandler
                    ):
                        self._handler = cls(self.config())
                        return self._handler
            except (ModuleNotFoundError, ImportError):
                pass
            # Fallback: base handler with provider config
            self._handler = BaseProviderHandler(self.config())
        return self._handler

    def resolve_base_url(self, data: dict | None = None) -> str:
        """Resolve effective base URL using handler."""
        return self.handler()._resolve_base_url(data)
