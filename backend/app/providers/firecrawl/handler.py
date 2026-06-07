"""Firecrawl provider handler."""

from app.providers.base import BaseProviderHandler


class FirecrawlHandler(BaseProviderHandler):
    """Handler for Firecrawl web fetch."""

    def build_webfetch_request(
        self, url: str, fmt: str, api_key: str,
    ) -> tuple[str, dict[str, str], str, dict | None]:
        """Build web fetch request for Firecrawl.

        Returns:
            (method, headers, full_url, body)
        """
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        fetch_url = f"{self.config.BASE_URL}/v1/scrape"
        body = {"url": url, "formats": [fmt]}
        return "POST", headers, fetch_url, body
