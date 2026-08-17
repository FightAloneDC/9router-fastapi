"""Fallback rotate must hard-cap attempts (farm burn guard)."""

from app.routers.v1_proxy.shared import MAX_FALLBACK_ATTEMPTS


def test_max_fallback_attempts_is_bounded() -> None:
    """Pool size must not imply unbounded rotate."""
    assert isinstance(MAX_FALLBACK_ATTEMPTS, int)
    assert MAX_FALLBACK_ATTEMPTS == 5


def test_proxy_routers_import_fallback_cap() -> None:
    """Chat + media endpoints share the same hard stop."""
    from app.routers.v1_proxy import audio, chat, embeddings, images
    from app.routers.v1_proxy import messages, responses

    for mod in (chat, messages, responses, embeddings, images, audio):
        assert getattr(mod, "MAX_FALLBACK_ATTEMPTS") == MAX_FALLBACK_ATTEMPTS
