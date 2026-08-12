"""Qoder refresh must persist expiresAt (ms/seconds aware)."""

from datetime import datetime, timezone

from app.providers.qoder.auth import (
    apply_qoder_token_expiry,
    expires_in_to_seconds,
)


def test_expires_in_ms_vs_seconds() -> None:
    assert expires_in_to_seconds(86400000) == 86400
    assert expires_in_to_seconds(3600) == 3600
    assert expires_in_to_seconds(None) is None
    assert expires_in_to_seconds("bad") is None


def test_apply_qoder_token_expiry_from_ms() -> None:
    data: dict = {}
    now = datetime(2026, 8, 12, 21, 0, 0, tzinfo=timezone.utc)
    apply_qoder_token_expiry(
        data,
        {
            "expires_in": 86400000,
            "refresh_token_expires_in": 172800000,
        },
        now=now,
    )
    assert data["expiresAt"].startswith("2026-08-13T21:00:00")
    assert data["refreshTokenExpiresAt"].startswith(
        "2026-08-14T21:00:00",
    )


def test_apply_qoder_token_expiry_prefers_absolute() -> None:
    data: dict = {}
    apply_qoder_token_expiry(
        data,
        {
            "expires_at": "2026-08-13T12:00:00Z",
            "refresh_token_expires_at": "2026-08-14T12:00:00Z",
            "expires_in": 1,
        },
    )
    assert data["expiresAt"] == "2026-08-13T12:00:00Z"
    assert data["refreshTokenExpiresAt"] == "2026-08-14T12:00:00Z"
