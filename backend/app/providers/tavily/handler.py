"""Tavily provider handler."""

from app.providers.base import BaseProviderHandler


class TavilyHandler(BaseProviderHandler):
    """Handler for Tavily web fetch."""

    def build_webfetch_request(
        self, url: str, fmt: str, api_key: str,
    ) -> tuple[str, dict[str, str], str, dict | None]:
        """Build web fetch request for Tavily.

        Returns:
            (method, headers, full_url, body)
        """
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        fetch_url = f"{self.config.BASE_URL}/extract"
        body = {"urls": [url], "format": fmt}
        return "POST", headers, fetch_url, body
