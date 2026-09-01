"""Custom-node catalog: SQL table, not connection blobs."""

from app.routers.providers.nodes import stale_model_lock_keys
from app.services.provider_models_store import uses_model_catalog_table


def test_custom_node_uses_catalog_table() -> None:
    """Nodes have no Provider config; catalog is still SQL."""
    assert uses_model_catalog_table(
        "openai-compatible-chat-108a0827fbc2",
    ) is True


def test_anthropic_node_uses_catalog_table() -> None:
    assert uses_model_catalog_table(
        "anthropic-compatible-abc123",
    ) is True


def test_stale_locks_match_node_id_and_old_prefix() -> None:
    node_id = "openai-compatible-chat-108a0827fbc2"
    data = {
        f"modelLock_{node_id}/moonshotai/Kimi-K3": {"until": 1},
        "modelLock_oldprefix/gpt-4": {"until": 1},
        "modelLock_commonstack/openai/gpt-5.6-luna": {"until": 1},
        "modelLock_gpt-4": {"until": 1},
        "apiKey": "secret",
    }
    stale = set(stale_model_lock_keys(
        data, node_id=node_id, old_prefix="oldprefix",
    ))
    assert f"modelLock_{node_id}/moonshotai/Kimi-K3" in stale
    assert "modelLock_oldprefix/gpt-4" in stale
    assert "modelLock_commonstack/openai/gpt-5.6-luna" not in stale
    assert "modelLock_gpt-4" not in stale
    assert "apiKey" not in stale
