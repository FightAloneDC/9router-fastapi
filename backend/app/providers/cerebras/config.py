from pydantic import BaseModel


class CerebrasConfig(BaseModel):
    """Cerebras-specific configuration. Loaded from .env file."""

    # Cerebras API key
    BASE_URL: str = "https://api.cerebras.ai/v1"
    API_KEY: str
    FORMAT: str = "openai"
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer"
    PROVIDER_ID: str = "cerebras"
    PROVIDER_NAME: str = "Cerebras"
    MODEL_PREFIX: str = "cb"
