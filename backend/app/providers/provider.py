"""Provider class — unified accessor for per-provider config and models.

Usage:
    from app.providers import PROVIDER_CEREBRAS
    from app.providers.provider import Provider

    p = Provider(PROVIDER_CEREBRAS)
    p.config()            # CerebrasConfig instance
    p.base_url()          # "https://api.cerebras.ai/v1"
    p.alias()             # "cb"
    p.parse_response({})  # []
    await p.fetch_models(api_key)
"""

import importlib

from pydantic import BaseModel


class Provider:
    """Unified accessor for provider config and models."""

    def __init__(self, name: str) -> None:
        self._name = name
        # Python module names cannot contain hyphens — convert to underscores
        self._module_name = name.replace("-", "_")
        self._config: BaseModel | None = None
        self._models = None

    def _load_config(self) -> BaseModel:
        if self._config is None:
            module = importlib.import_module(f"app.providers.{self._module_name}.config")
            # Convention: first class ending with "Config" in the module
            for attr in dir(module):
                if attr.endswith("Config"):
                    cls = getattr(module, attr)
                    if isinstance(cls, type) and issubclass(cls, BaseModel):
                        self._config = cls()
                        return self._config
            raise ValueError(f"No Config class found in app.providers.{self._module_name}.config")
        return self._config

    def _load_models(self):
        if self._models is None:
            self._models = importlib.import_module(f"app.providers.{self._module_name}.models")
        return self._models

    def config(self) -> BaseModel:
        """Return the provider's config instance."""
        return self._load_config()

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
