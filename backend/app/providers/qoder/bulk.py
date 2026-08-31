"""Bulk import of grok-farm-modular Qoder account exports.

Qoder farm entries mirror the Grok farm shape (``email`` +
``tokens``) but carry Qoder identity and optional trial/quota
snapshot fields in ``tokens``.
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

    checked_quota = tokens.get("checked_quota")
    if checked_quota is None:
        checked_quota = entry.get("checked_quota")
    psd = {
        "loginMethod": "bulk_import",
        "userId": tokens.get("user_id"),
        "machineId": tokens.get("machine_id"),
        "plan": tokens.get("plan"),
        "userType": tokens.get("userType"),
        "proTrialStartAt": parse_expires_at(
            tokens.get("pro_trial_start_at"),
        ),
        "proTrialEndAt": parse_expires_at(
            tokens.get("pro_trial_end_at"),
        ),
        "farmQuotaTotal": _optional_int(checked_quota),
        "farmQuotaRemaining": _optional_int(
            tokens.get("quota_remaining"),
        ),
        "farmQuotaExceeded": _optional_bool(
            tokens.get("is_quota_exceeded"),
        ),
        "personalToken": _optional_pat(
            tokens.get("personal_token"),
        ),
    }
    token_data = {
        "accessToken": access_token,
        "refreshToken": tokens.get("refresh_token"),
        "scope": tokens.get("scope"),
        "email": email,
        # Bulk-imported accounts are identified by email, not the
        # farm-provided display name
        "displayName": email,
        "providerSpecificData": {
            key: value
            for key, value in psd.items()
            if value is not None
        },
    }
    return {
        "email": email,
        "token_data": token_data,
        "expires_at": parse_expires_at(tokens.get("expires_at")),
    }


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_pat(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token:
        return None
    return token
