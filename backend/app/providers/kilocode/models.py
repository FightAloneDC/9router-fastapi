"""Kilocode model fetching — public gateway, no auth required."""

import httpx

KILO_GATEWAY_MODELS_URL = "https://api.kilo.ai/api/gateway/models"


def parse_response(data: dict) -> list[dict]:
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch free models from Kilo public gateway (no auth)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(KILO_GATEWAY_MODELS_URL, headers={"Accept": "application/json"})
        resp.raise_for_status()
        all_models = resp.json().get("data", [])
        return [
            {"id": m["id"], "name": m.get("name", m["id"]), "type": "llm"}
            for m in all_models
            if m.get("id") and m.get("isFree", False)
        ]
