"""Jina Reader provider handler."""

from app.providers.base import BaseProviderHandler


class JinaReaderHandler(BaseProviderHandler):
    """Handler for Jina Reader web fetch."""

    def build_webfetch_request(
        self, url: str, fmt: str, api_key: str,
    ) -> tuple[str, dict[str, str], str, dict | None]:
        """Build web fetch request for Jina Reader.

        Returns:
            (method, headers, full_url, body)
        """
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        fetch_url = f"{self.config.BASE_URL}/{url}"
        return "GET", headers, fetch_url, None
