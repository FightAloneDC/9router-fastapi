"""Unit tests for qoder farm-export bulk import parsing."""

from datetime import datetime, timedelta, timezone

import pytest

from app.providers.qoder.bulk import parse_farm_entry


def _farm_entry(**overrides) -> dict:
    future = datetime.now(timezone.utc) + timedelta(hours=6)
    entry = {
        "email": "User@Example.com",
        "password": "secret",
        "proxy": "1.2.3.4:8080",
        "tokens": {
            "access_token": "at-abc",
            "refresh_token": "rt-abc",
            "expires_at": future.isoformat(),
            "expires_in": 21600,
            "email": "user@example.com",
            "display_name": "User Example",
            "machine_id": "machine-123",
            "personal_token": "pt-abc",
            "plan": "pro",
            "scope": "openid",
            "user_id": "user-456",
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
        assert psd["loginMethod"] == "bulk_import"
        assert psd["userId"] == "user-456"
        assert psd["machineId"] == "machine-123"
        assert psd["plan"] == "pro"
        assert parsed["expires_at"] is not None
        assert "proTrialEndAt" not in psd
        assert "farmQuotaTotal" not in psd
        assert psd["personalToken"] == "pt-abc"
        assert "personal_token" not in token_data
        assert "password" not in token_data

    def test_optional_trial_and_quota_snapshot(self):
        entry = _farm_entry()
        entry["checked_quota"] = 300
        entry["tokens"].update({
            "userType": "personal_professional_trial",
            "plan": "PLAN_TIER_PRO_TRIAL",
            "pro_trial_start_at": "2026-08-18T10:59:32.131000Z",
            "pro_trial_end_at": "2026-09-01T10:59:32.131000Z",
            "checked_quota": 300,
            "is_quota_exceeded": False,
            "quota_remaining": 257,
        })
        psd = parse_farm_entry(entry)["token_data"][
            "providerSpecificData"
        ]
        assert psd["userType"] == "personal_professional_trial"
        assert psd["plan"] == "PLAN_TIER_PRO_TRIAL"
        assert psd["proTrialStartAt"] is not None
        assert psd["proTrialEndAt"] is not None
        assert psd["farmQuotaTotal"] == 300
        assert psd["farmQuotaRemaining"] == 257
        assert psd["farmQuotaExceeded"] is False

    def test_missing_personal_token_still_parses(self):
        entry = _farm_entry()
        entry["tokens"].pop("personal_token")
        parsed = parse_farm_entry(entry)
        psd = parsed["token_data"]["providerSpecificData"]
        assert "personalToken" not in psd

    def test_checked_quota_falls_back_to_root(self):
        entry = _farm_entry()
        entry["checked_quota"] = 300
        psd = parse_farm_entry(entry)["token_data"][
            "providerSpecificData"
        ]
        assert psd["farmQuotaTotal"] == 300

    def test_display_name_is_always_email(self):
        # Farm display_name is ignored; email is the identity
        parsed = parse_farm_entry(_farm_entry())
        assert parsed["token_data"]["displayName"] == "user@example.com"
        entry = _farm_entry()
        entry["tokens"].pop("display_name")
        parsed = parse_farm_entry(entry)
        assert parsed["token_data"]["displayName"] == "user@example.com"

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
