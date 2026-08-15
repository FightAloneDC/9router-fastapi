"""Connection accountType lives in the JSON blob, not a column."""

import pytest

from app.routers.providers.constants import (
    ACCOUNT_TYPES,
    DEFAULT_ACCOUNT_TYPE,
    normalize_account_type,
)


def test_known_account_types() -> None:
    assert ACCOUNT_TYPES == ("free", "payg", "subscribe")
    assert DEFAULT_ACCOUNT_TYPE == "free"
    assert normalize_account_type("PAYG") == "payg"
    assert normalize_account_type("  Free ") == "free"
    assert normalize_account_type("subscribe") == "subscribe"


def test_blank_defaults_to_free() -> None:
    assert normalize_account_type(None) is None
    assert normalize_account_type("") == "free"
    with pytest.raises(ValueError):
        normalize_account_type("enterprise")
