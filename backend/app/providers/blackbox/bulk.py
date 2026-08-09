"""Bulk import of Blackbox AI API keys.

Accepted entry formats (one per line in the UI textarea):

    <api_key>
    <api_key>|<name>

Plain API keys carry no account identity, so connections are
deduplicated by the key itself and named either from the
``|name`` suffix or from a masked version of the key (full keys
must never appear in connection lists).
"""

from __future__ import annotations

from typing import Any


def parse_api_key_entry(entry: Any) -> dict:
    """Normalize one bulk entry to ``{"api_key", "name"}``.

    Accepts a string (``key`` or ``key|name``) or an object with
    ``apiKey``/``api_key``/``key`` and optional ``name``.

    Raises:
        ValueError: when the entry carries no usable API key.
    """
    name: str | None = None
    if isinstance(entry, dict):
        key = (
            entry.get("apiKey")
            or entry.get("api_key")
            or entry.get("key")
        )
        raw_name = entry.get("name")
        if isinstance(raw_name, str) and raw_name.strip():
            name = raw_name.strip()
    elif isinstance(entry, str):
        line = entry.strip()
        if not line:
            raise ValueError("Empty line")
        key, sep, raw_name = line.partition("|")
        key = key.strip()
        if sep and raw_name.strip():
            name = raw_name.strip()
    else:
        raise ValueError("Entry is not a string or object")

    if not key or not isinstance(key, str):
        raise ValueError("Missing API key")
    return {"api_key": key.strip(), "name": name}


def mask_key(key: str) -> str:
    """Default display name — never expose the full key."""
    if len(key) <= 10:
        return f"{key[:2]}***"
    return f"{key[:6]}...{key[-4:]}"
