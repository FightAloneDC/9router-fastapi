"""Exa provider handler."""

from app.providers.base import BaseProviderHandler


class ExaHandler(BaseProviderHandler):
    """Handler for Exa web fetch."""

    def build_webfetch_request(
        self, url: str, fmt: str, api_key: str,
    ) -> tuple[str, dict[str, str], str, dict | None]:
        """Build web fetch request for Exa.

        Returns:
            (method, headers, full_url, body)
        """
        headers: dict[str, str] = {}
        if api_key:
            headers["x-api-key"] = api_key
        fetch_url = f"{self.config.BASE_URL}/contents"
        body = {"urls": [url], "text": True}
        return "POST", headers, fetch_url, body
