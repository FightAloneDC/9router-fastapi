"""Provider package.

Each provider lives in its own sub-package (e.g. provider/openrouter/).
PROVIDER_MODELS_CONFIG aggregates all provider configs for backward compatibility.
"""

from app.providers.base import ProviderModelFetchConfig
from app.providers.cerebras.config import config as cerebras
from app.providers.openrouter.config import config as openrouter

PROVIDER_MODELS_CONFIG: dict[str, ProviderModelFetchConfig] = {
    "cerebras": cerebras,
    "openrouter": openrouter,
}

__all__ = ["ProviderModelFetchConfig", "PROVIDER_MODELS_CONFIG"]
