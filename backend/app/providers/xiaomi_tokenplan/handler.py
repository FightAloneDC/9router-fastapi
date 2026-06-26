"""Xiaomi TokenPlan handler — region-aware base URL resolution."""

from app.providers.base import BaseProviderHandler


class XiaomiTokenplanHandler(BaseProviderHandler):
    """Handler for Xiaomi TokenPlan provider (region-aware)."""

    REGION_URLS = {
        "sgp": "https://token-plan-sgp.xiaomimimo.com/v1",
        "cn": "https://token-plan-cn.xiaomimimo.com/v1",
        "ams": "https://token-plan-ams.xiaomimimo.com/v1",
    }

    def _resolve_base_url(self, data: dict | None = None) -> str:
        if data:
            # Region can be at top level or inside providerSpecificData
            psd = data.get("providerSpecificData", {})
            region = data.get("region") or psd.get("region", "sgp")
            if region in self.REGION_URLS:
                return self.REGION_URLS[region].rstrip("/")
            if data.get("baseUrl"):
                return data["baseUrl"].rstrip("/")
        return super()._resolve_base_url(data)

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        from app.providers.model_helpers import fetch_models_header_auth
        from app.providers.base import BaseProviderConfig

        if not api_key:
            raise ValueError("No API key configured")

        base_url = self._resolve_base_url(data)
        config = BaseProviderConfig(
            PROVIDER_NAME="Xiaomi TokenPlan",
            PROVIDER_ID="xiaomi-tokenplan",
            ALIAS="xmtp",
            BASE_URL=base_url,
            AUTH_HEADER=self.config.AUTH_HEADER,
            AUTH_PREFIX=self.config.AUTH_PREFIX,
        )
        models_raw = await fetch_models_header_auth(config, api_key)
        return [self._normalize_model(m) for m in models_raw if self._normalize_model(m).get("id")]
