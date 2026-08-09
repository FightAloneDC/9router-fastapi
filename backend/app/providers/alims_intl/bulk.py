"""Bulk import of Alibaba Studio farm account exports.

Farm entries carry ``email`` + ``api_key`` at the top level (plus
optional metadata like password, proxy, host, etc).

Example::

    [
      {
        "email": "user@example.com",
        "api_key": "sk-xxx",
        "host": "ws-xxx.maas.aliyuncs.com"
      }
    ]

Email is mandatory — connections are identified and deduplicated by
email within the provider scope.
"""

from __future__ import annotations

from typing import Any

from app.providers.grok_cli.bulk import parse_expires_at


def parse_farm_entry(entry: Any) -> dict:
    """Normalize one Alibaba Studio farm account entry.

    Returns the same shape as the grok-cli parser: ``email``
    (lowercased), ``token_data`` (accepted by the
    ``_save_connection`` helper) and ``expires_at``.

    Raises:
        ValueError: when the entry is not a valid farm account.
    """
    if not isinstance(entry, dict):
        raise ValueError("Entry is not an object")

    api_key = entry.get("api_key") or entry.get("apiKey")
    if not api_key or not isinstance(api_key, str):
        raise ValueError("Missing api_key")

    email = entry.get("email")
    if not email or not isinstance(email, str):
        raise ValueError("Missing email")
    email = email.strip().lower()

    token_data = {
        "apiKey": api_key,
        "email": email,
        "displayName": email,
        "providerSpecificData": {
            "authMethod": "bulk_import",
            "email": email,
        },
    }
    return {
        "email": email,
        "token_data": token_data,
        "expires_at": parse_expires_at(entry.get("expires_at")),
    }
