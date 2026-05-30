"""Provider helper — unified accessor for provider configs.

Usage:
    Provider('cerebras').base_url()   # -> "https://api.cerebras.ai/v1"
    Provider('cerebras').prefix()     # -> "cb"
    Provider('cerebras').set_models(["llama3.1-8b", "llama3.1-70b"])
    Provider('cerebras').models()     # -> ["llama3.1-8b", "llama3.1-70b"]
"""

from typing import Type

from pydantic import BaseModel

from app.providers.cerebras.config import CerebrasConfig

# Registry: provider name -> config class
_REGISTRY: dict[str, Type[BaseModel]] = {
    "cerebras": CerebrasConfig,
}


class Provider:
    """Unified accessor for provider configs."""

    def __init__(self, name: str) -> None:
        if name not in _REGISTRY:
            raise ValueError(f"Unknown provider: {name}")
        self._name = name
        self._config = _REGISTRY[name]()

    def base_url(self) -> str:
        """Return provider base URL."""
        return self._config.BASE_URL

    def prefix(self) -> str:
        """Return model prefix for routing."""
        return self._config.MODEL_PREFIX

    def set_models(self, models: list[str]) -> None:
        """Update default models list."""
        self._config = self._config.model_copy(update={"DEFAULT_MODELS": models})

    def models(self) -> list[str]:
        """Return current default models."""
        return self._config.DEFAULT_MODELS

    def config(self) -> BaseModel:
        """Return full config object."""
        return self._config
