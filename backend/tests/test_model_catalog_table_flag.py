"""Flag: only OpenRouter uses provider_models catalog table."""

from app.services.provider_models_store import (
    parse_history_entry,
    prune_history,
    resolve_enabled_flag,
    uses_model_catalog_table,
)


def test_openrouter_uses_catalog_table() -> None:
    assert uses_model_catalog_table("openrouter") is True


def test_mistral_stays_on_blobs() -> None:
    assert uses_model_catalog_table("mistral") is False


def test_grok_cli_stays_on_blobs() -> None:
    assert uses_model_catalog_table("grok-cli") is False


def test_fetch_without_history_is_disabled() -> None:
    assert resolve_enabled_flag("a", {}, {}) is False


def test_fetch_keeps_row_flag() -> None:
    assert resolve_enabled_flag("a", {"a": True}, {}) is True
    assert resolve_enabled_flag("b", {"b": False}, {}) is False


def test_fetch_after_clear_uses_history() -> None:
    history = {"keep": True, "off": False}
    assert resolve_enabled_flag("keep", {}, history) is True
    assert resolve_enabled_flag("off", {}, history) is False
    assert resolve_enabled_flag("new", {}, history) is False


def test_prune_drops_removed_upstream_keeps_custom() -> None:
    history = {
        "gone": {"enabled": True, "custom": False},
        "live": {"enabled": False, "custom": False},
        "mine": {"enabled": True, "custom": True},
    }
    pruned = prune_history(history, {"live"}, {"mine"})
    assert "gone" not in pruned
    assert pruned["live"]["custom"] is False
    assert pruned["mine"]["custom"] is True


def test_parse_history_bool_and_object() -> None:
    assert parse_history_entry(True) == (True, False)
    assert parse_history_entry(
        {"enabled": False, "custom": True},
    ) == (False, True)


def test_openrouter_uses_catalog_table() -> None:
    assert uses_model_catalog_table("openrouter") is True


def test_mistral_stays_on_blobs() -> None:
    assert uses_model_catalog_table("mistral") is False


def test_grok_cli_stays_on_blobs() -> None:
    assert uses_model_catalog_table("grok-cli") is False
