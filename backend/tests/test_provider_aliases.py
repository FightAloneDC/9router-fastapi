"""DB prefix overlay: missing row uses config."""

from app.services.provider_aliases import (
    overlay_alias_to_id,
    overlay_alias_to_ids,
    overlay_id_to_alias,
    set_overrides,
)


def test_missing_db_keeps_config() -> None:
    set_overrides({})
    merged = overlay_id_to_alias({"openrouter": "openrouter"})
    assert merged["openrouter"] == "openrouter"
    routed = overlay_alias_to_id({"openrouter": "openrouter"})
    assert routed["openrouter"] == "openrouter"


def test_db_replaces_config_prefix() -> None:
    set_overrides({"openrouter": "or"})
    try:
        merged = overlay_id_to_alias({"openrouter": "openrouter"})
        assert merged["openrouter"] == "or"
        routed = overlay_alias_to_id({"openrouter": "openrouter"})
        assert routed["or"] == "openrouter"
        assert routed["openrouter"] == "openrouter"
        ids = overlay_alias_to_ids({"openrouter": ["openrouter"]})
        assert ids["or"] == ["openrouter"]
    finally:
        set_overrides({})
