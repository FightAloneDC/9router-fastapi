from app.providers.base import ProviderModelFetchConfig

config = ProviderModelFetchConfig(
    url="https://openrouter.ai/api/v1/models",
    headers={"Content-Type": "application/json"},
    authHeader="Authorization",
    authPrefix="Bearer ",
    responseKey="data",
)
