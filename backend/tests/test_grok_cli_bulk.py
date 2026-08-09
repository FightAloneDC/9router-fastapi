"""Unit tests for grok-farm-modular bulk import parsing."""

from datetime import datetime, timedelta, timezone

import pytest

from app.providers.grok_cli.bulk import (
    is_expired,
    parse_expires_at,
    parse_farm_entry,
)


def _farm_entry(**overrides) -> dict:
    future = datetime.now(timezone.utc) + timedelta(hours=6)
    entry = {
        "email": "User@Example.com",
        "password": "secret",
        "proxy": "1.2.3.4:8080",
        "tokens": {
            "access_token": "at-abc",
            "refresh_token": "rt-abc",
            "id_token": "id-abc",
            "expires_at": future.isoformat(),
            "expires_in": 21600,
            "email": "user@example.com",
            "scope": "openid grok-cli:access",
        },
    }
    entry.update(overrides)
    return entry


class TestParseFarmEntry:
    def test_valid_entry(self):
        parsed = parse_farm_entry(_farm_entry())
        assert parsed["email"] == "user@example.com"
        token_data = parsed["token_data"]
        assert token_data["accessToken"] == "at-abc"
        assert token_data["refreshToken"] == "rt-abc"
        assert token_data["email"] == "user@example.com"
        assert token_data["displayName"] == "user@example.com"
        psd = token_data["providerSpecificData"]
        assert psd["authMethod"] == "bulk_import"
        assert psd["idToken"] == "id-abc"
        assert parsed["expires_at"] is not None

    def test_email_falls_back_to_tokens(self):
        entry = _farm_entry()
        del entry["email"]
        parsed = parse_farm_entry(entry)
        assert parsed["email"] == "user@example.com"

    def test_not_an_object(self):
        with pytest.raises(ValueError, match="not an object"):
            parse_farm_entry(["nope"])

    def test_missing_tokens(self):
        entry = _farm_entry()
        del entry["tokens"]
        with pytest.raises(ValueError, match="tokens"):
            parse_farm_entry(entry)

    def test_missing_access_token(self):
        entry = _farm_entry()
        del entry["tokens"]["access_token"]
        with pytest.raises(ValueError, match="access_token"):
            parse_farm_entry(entry)

    def test_missing_email(self):
        entry = _farm_entry(email=None)
        del entry["tokens"]["email"]
        with pytest.raises(ValueError, match="email"):
            parse_farm_entry(entry)


class TestParseExpiresAt:
    def test_z_suffix(self):
        result = parse_expires_at("2026-08-08T02:54:43.710621Z")
        assert result == "2026-08-08T02:54:43.710621+00:00"

    def test_naive_becomes_utc(self):
        result = parse_expires_at("2026-08-08T02:54:43")
        assert result.endswith("+00:00")

    def test_invalid(self):
        assert parse_expires_at("not-a-date") is None

    def test_missing(self):
        assert parse_expires_at(None) is None


class TestIsExpired:
    def test_past(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        assert is_expired(past.isoformat()) is True

    def test_future(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert is_expired(future.isoformat()) is False

    def test_none_is_not_expired(self):
        assert is_expired(None) is False
