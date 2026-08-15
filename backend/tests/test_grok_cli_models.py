"""Grok CLI /models parsing drops non-API ids."""

from app.providers.grok_cli.models import parse_response


def test_parse_drops_grok_build_product_id() -> None:
    models = parse_response({
        "data": [
            {"id": "grok-build"},
            {"id": "grok-4.6"},
            {"id": "grok-build-0.1"},
        ],
    })
    ids = [m["id"] for m in models]
    assert "grok-build" not in ids
    assert ids == ["grok-4.6", "grok-build-0.1"]
