"""Keelcode handler — Bearer token + Anthropic Messages API."""

from __future__ import annotations

import time

import httpx

from app.providers.base import (
    BaseProviderHandler,
    ValidateResult,
)
from app.services.outbound_proxy import create_upstream_client


class KeelcodeHandler(BaseProviderHandler):
    """Handler for Keelcode (OAuth device-code + Messages API).

    Auth: Authorization Bearer (device session or API key).
    Upstream chat path: POST /v1/messages (FORMAT=claude).
    Validate: GET /v1/models.
    """

    async def validate(
        self,
        api_key: str,
        data: dict | None = None,
    ) -> ValidateResult:
        if not api_key:
            return ValidateResult(
                valid=False,
                error="No access token configured",
            )

        start = time.monotonic()
        base_url = self._resolve_base_url(data)
        if base_url.endswith("/messages"):
            base_url = base_url[: -len("/messages")]
        url = f"{base_url.rstrip('/')}/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            **(self.config.EXTRA_HEADERS or {}),
        }

        try:
            async with create_upstream_client(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                latency = int(
                    (time.monotonic() - start) * 1000
                )
                if resp.status_code == 200:
                    return ValidateResult(
                        valid=True, latency_ms=latency
                    )
                if resp.status_code in (401, 403):
                    return ValidateResult(
                        valid=False,
                        error="Token invalid or revoked",
                        latency_ms=latency,
                    )
                return ValidateResult(
                    valid=False,
                    error=f"API returned {resp.status_code}",
                    latency_ms=latency,
                )
        except httpx.ConnectError:
            return ValidateResult(
                valid=False,
                error="Cannot connect to Keelcode API",
                latency_ms=int(
                    (time.monotonic() - start) * 1000
                ),
            )
        except httpx.TimeoutException:
            return ValidateResult(
                valid=False,
                error="Connection timed out",
                latency_ms=int(
                    (time.monotonic() - start) * 1000
                ),
            )
        except Exception as e:
            return ValidateResult(
                valid=False,
                error=str(e)[:200],
                latency_ms=int(
                    (time.monotonic() - start) * 1000
                ),
            )

    async def fetch_models(
        self,
        api_key: str,
        data: dict | None = None,
    ) -> list[dict]:
        from app.providers.keelcode.models import (
            fetch_models as _fetch,
        )

        return await _fetch(api_key, data=data)

    def build_upstream_url(
        self,
        base_url: str,
        stream: bool = False,
        data: dict | None = None,
        model: str = "",
    ) -> str:
        """Keelcode uses Anthropic-compatible /messages."""
        return f"{base_url.rstrip('/')}/messages"
