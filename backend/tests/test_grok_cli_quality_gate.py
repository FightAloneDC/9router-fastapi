"""Grok CLI literal-407 quality gate."""

from __future__ import annotations

from app.providers.grok_cli.quality_gate import (
    assistant_text_from_completed,
    completed_from_sse,
    probe_passes,
)


def _completed(text: str) -> dict:
    return {
        "output": [{
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": text,
            }],
        }],
    }


def test_probe_passes_only_exact_407() -> None:
    assert probe_passes("407") is True
    assert probe_passes(" 407 \n") is True
    assert probe_passes("202") is False
    assert probe_passes("407.") is False
    assert probe_passes("reply exactly with : 407") is False
    assert probe_passes("") is False


def test_assistant_text_from_completed() -> None:
    assert assistant_text_from_completed(
        _completed("407"),
    ).strip() == "407"
    assert assistant_text_from_completed(
        _completed("202"),
    ).strip() == "202"
    tools = {
        "output": [{
            "type": "function_call",
            "name": "x",
            "arguments": "{}",
        }],
    }
    assert assistant_text_from_completed(tools) == ""


def test_completed_from_sse() -> None:
    sse = (
        "data: {\"type\":\"response.created\"}\n"
        "data: {\"type\":\"response.completed\","
        "\"response\":{\"output\":[{"
        "\"type\":\"message\",\"content\":[{"
        "\"type\":\"output_text\",\"text\":\"407\""
        "}]}]}}\n"
        "data: [DONE]\n"
    )
    completed = completed_from_sse(sse)
    assert probe_passes(assistant_text_from_completed(completed))
