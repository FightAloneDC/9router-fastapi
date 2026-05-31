"""URL utilities for building upstream endpoints."""

from urllib.parse import urlparse, urlunparse


def url_path_join(base: str, *parts: str) -> str:
    """Join a base URL with path segments, preserving the base path.

    Unlike urllib.parse.urljoin, this does NOT discard the base path
    when joining with a relative segment.

    Args:
        base: Base URL (e.g. "https://api.cerebras.ai/v1").
        *parts: Path segments to append (e.g. "models", "chat/completions").

    Returns:
        Joined URL with scheme defaulted to https if missing.

    Raises:
        ValueError: If base is empty.

    Examples:
        >>> url_path_join("api.cerebras.ai/v1", "models")
        "https://api.cerebras.ai/v1/models"
        >>> url_path_join("https://api.cerebras.ai/v1/", "/models")
        "https://api.cerebras.ai/v1/models"
        >>> url_path_join("https://api.cerebras.ai/v1", "chat", "completions")
        "https://api.cerebras.ai/v1/chat/completions"
        >>> url_path_join("https://api.example.com/v1?key=x", "models")
        "https://api.example.com/v1/models?key=x"
    """
    if not base or not base.strip():
        raise ValueError("base URL cannot be empty")

    parsed = urlparse(base.strip())

    scheme = parsed.scheme or "https"

    # Build path: strip trailing slash from base, strip leading/trailing from parts
    path = parsed.path.rstrip("/")
    for p in parts:
        segment = p.strip("/")
        if segment:
            path = f"{path}/{segment}"

    return urlunparse((scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
