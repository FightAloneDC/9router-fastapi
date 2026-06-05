"""Amazon Bedrock model fetching — needs AWS region/signing."""

from app.providers.amazon_bedrock.config import AmazonBedrockConfig

_config: AmazonBedrockConfig = AmazonBedrockConfig()


def parse_response(data: dict) -> list[dict]:
    """Bedrock returns {modelSummaries: [...]}."""
    models: list[dict] = []
    for m in data.get("modelSummaries", []):
        if isinstance(m, dict):
            models.append({
                "id": m.get("modelId", ""),
                "name": m.get("modelName", ""),
                "type": "llm",
            })
    return models


async def fetch_models(api_key: str) -> list[dict]:
    """Bedrock needs AWS signing — handled at endpoint level."""
    return []
