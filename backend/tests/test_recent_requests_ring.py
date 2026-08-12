"""Recent-request ring buffer order for live /usage updates."""

from app.services import active_requests as ar


def test_push_recent_newest_first(monkeypatch) -> None:
    ar._recent_requests.clear()
    ar.push_recent_request("grok-cli", "grok-4.5", 1, 2)
    ar.push_recent_request("alims-intl", "deepseek", 3, 4)
    recent = ar.get_recent_requests()
    assert len(recent) == 2
    assert recent[0]["provider"] == "alims-intl"
    assert recent[0]["model"] == "deepseek"
    assert recent[1]["provider"] == "grok-cli"
    assert recent[0]["id"] and recent[0]["id"] != recent[1]["id"]
    assert recent[0]["timestamp"].endswith("Z")
    assert "." in recent[0]["timestamp"]  # millisecond precision
