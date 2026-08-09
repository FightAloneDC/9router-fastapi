"""Bulk import of grok-farm-modular account exports.

grok-farm-modular exports a JSON list of farmed xAI accounts. Each
entry carries an ``email`` and a ``tokens`` dict in the auth.x.ai
OIDC shape (access/refresh/id token, expiry, scope) — the same shape
the device-code OAuth flow produces.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_farm_entry(entry: Any) -> dict:
    """Normalize one grok-farm account entry.

    Returns:
        dict with keys ``email`` (lowercased), ``token_data`` (shape
        accepted by the OAuth ``_save_connection`` helper) and
        ``expires_at`` (ISO string, absolute access-token expiry).

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
        # Farm accounts have no display name — email doubles as name
        "displayName": email,
        "providerSpecificData": {
            "authMethod": "bulk_import",
            "idToken": tokens.get("id_token"),
            "email": email,
        },
    }
    return {
        "email": email,
        "token_data": token_data,
        "expires_at": parse_expires_at(tokens.get("expires_at")),
    }


def parse_expires_at(value: Any) -> str | None:
    """Normalize an ISO ``expires_at``; None when absent or invalid."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def is_expired(expires_at: str | None) -> bool:
    """True when the access token expiry is in the past."""
    if not expires_at:
        return False
    dt = datetime.fromisoformat(expires_at)
    return dt <= datetime.now(timezone.utc)
