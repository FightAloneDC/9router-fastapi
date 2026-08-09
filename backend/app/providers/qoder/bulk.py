"""Bulk import of grok-farm-modular Qoder account exports.

Qoder farm entries mirror the Grok farm shape (``email`` + ``tokens``)
but carry Qoder identity fields in ``tokens`` (user_id, machine_id,
plan, display_name).
"""

from __future__ import annotations

from typing import Any

# Shared farm-import expiry helpers
from app.providers.grok_cli.bulk import parse_expires_at


def parse_farm_entry(entry: Any) -> dict:
    """Normalize one qoder farm account entry.

    Returns the same shape as the grok-cli parser: ``email``
    (lowercased), ``token_data`` (accepted by the OAuth
    ``_save_connection`` helper) and ``expires_at``.

    Raises:
        ValueError: when the entry is not a valid farm account.
    """
    if not isinstance(entry, dict):
        raise ValueError("Entry is not an object")
    tokens = entry.get("tokens")
    if not isinstance(tokens, dict):
        raise ValueError("Missing tokens object")
    access_token = tokens.get("access_token")
    if not access_token or not isinstance(access_token, str):
        raise ValueError("Missing tokens.access_token")

    email = entry.get("email") or tokens.get("email")
    if not email or not isinstance(email, str):
        raise ValueError("Missing email")
    email = email.strip().lower()

    token_data = {
        "accessToken": access_token,
        "refreshToken": tokens.get("refresh_token"),
        "scope": tokens.get("scope"),
        "email": email,
        # Bulk-imported accounts are identified by email, not the
        # farm-provided display name
        "displayName": email,
        "providerSpecificData": {
            "loginMethod": "bulk_import",
            "userId": tokens.get("user_id"),
            "machineId": tokens.get("machine_id"),
            "plan": tokens.get("plan"),
        },
    }
    return {
        "email": email,
        "token_data": token_data,
        "expires_at": parse_expires_at(tokens.get("expires_at")),
    }
