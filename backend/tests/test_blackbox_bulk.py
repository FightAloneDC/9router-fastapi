"""Unit tests for Blackbox API key bulk import parsing."""

import pytest

from app.providers.blackbox.bulk import (
    mask_key,
    parse_api_key_entry,
)


def test_parse_plain_key():
    parsed = parse_api_key_entry("bb_key_abc123")
    assert parsed == {"api_key": "bb_key_abc123", "name": None}


def test_parse_key_with_name():
    parsed = parse_api_key_entry("bb_key_abc123|Work account")
    assert parsed == {
        "api_key": "bb_key_abc123",
        "name": "Work account",
    }


def test_parse_strips_whitespace():
    parsed = parse_api_key_entry("  bb_key_abc123 |  My Key  ")
    assert parsed == {"api_key": "bb_key_abc123", "name": "My Key"}


def test_parse_empty_name_falls_back():
    parsed = parse_api_key_entry("bb_key_abc123|")
    assert parsed == {"api_key": "bb_key_abc123", "name": None}


def test_parse_object_entry():
    parsed = parse_api_key_entry(
        {"apiKey": "bb_key_abc123", "name": "Obj"}
    )
    assert parsed == {"api_key": "bb_key_abc123", "name": "Obj"}


def test_parse_object_alt_keys():
    parsed = parse_api_key_entry({"key": "bb_key_abc123"})
    assert parsed == {"api_key": "bb_key_abc123", "name": None}


def test_parse_rejects_empty_line():
    with pytest.raises(ValueError):
        parse_api_key_entry("   ")


def test_parse_rejects_missing_key():
    with pytest.raises(ValueError):
        parse_api_key_entry({"name": "no key"})
    with pytest.raises(ValueError):
        parse_api_key_entry(42)


def test_mask_key():
    assert mask_key("bb_key_abcdef123456") == "bb_key...3456"
    assert mask_key("short") == "sh***"
