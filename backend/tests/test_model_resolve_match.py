"""Regression: bare model resolve must not invent a wrong provider."""

from app.services.proxy import (
    _conn_model_ids,
    _connection_has_model,
)


def test_conn_model_ids_accepts_string_and_dict() -> None:
    assert _conn_model_ids(["gpt-4", ""]) == {"gpt-4"}
    assert _conn_model_ids([
        {"id": "grok-4.5", "type": "llm"},
        {"id": "", "type": "llm"},
        "legacy",
        None,
        42,
    ]) == {"grok-4.5", "legacy"}


def test_connection_has_model_matches_dict_ids() -> None:
    grok_models = [
        {"id": "grok-4.5", "type": "llm"},
        {"id": "grok-4.6", "type": "llm"},
    ]
    alims_models = [
        {"id": "deepseek-v4-flash-0731", "type": "llm"},
        {"id": "qwen3.8-max", "type": "llm"},
    ]
    assert _connection_has_model(grok_models, "grok-cli", "grok-4.5")
    assert not _connection_has_model(
        alims_models, "alims-intl", "grok-4.5",
    )
    assert _connection_has_model(
        ["alims-intl/qwen3"], "alims-intl", "qwen3",
    )
