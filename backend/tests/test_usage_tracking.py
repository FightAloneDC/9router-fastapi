"""Tests for usage tracking — validates success criteria from docs/usage-fix-plan.md.

Success Criteria:
1. Recent Requests shows same data as Details tab
2. Canvas edges animate during active requests (active_requests service)
3. Cost calculation covers 90%+ of common models
4. Data consistency between usage_history and request_details
5. No data loss during tracking failures (transaction rollback)
"""

import pytest
from app.services.active_requests import track_request_start, track_request_end, get_active_requests


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: track_request_start/end lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def test_track_request_lifecycle():
    """Test that active request tracking works correctly."""
    # Start tracking
    req_id = track_request_start("openai", "gpt-4o")
    assert req_id is not None
    assert "openai" in req_id
    assert "gpt-4o" in req_id

    # Should be in active list
    active = get_active_requests()
    assert len(active) >= 1
    matching = [r for r in active if r["provider"] == "openai" and r["model"] == "gpt-4o"]
    assert len(matching) >= 1
    assert matching[0]["provider"] == "openai"
    assert matching[0]["model"] == "gpt-4o"
    assert "startedAt" in matching[0]

    # End tracking
    track_request_end(req_id)

    # Should be removed from active list
    active_after = get_active_requests()
    matching_after = [r for r in active_after if r["provider"] == "openai" and r["model"] == "gpt-4o"]
    assert len(matching_after) == 0


def test_track_request_multiple():
    """Test tracking multiple concurrent requests."""
    id1 = track_request_start("anthropic", "claude-sonnet-4")
    id2 = track_request_start("deepseek", "deepseek-chat")

    active = get_active_requests()
    providers = {r["provider"] for r in active}
    assert "anthropic" in providers
    assert "deepseek" in providers

    track_request_end(id1)
    track_request_end(id2)

    active_after = get_active_requests()
    providers_after = {r["provider"] for r in active_after}
    assert "anthropic" not in providers_after
    assert "deepseek" not in providers_after


def test_track_request_end_nonexistent():
    """Test ending a non-existent request doesn't crash."""
    # Should not raise
    track_request_end("non-existent-id-12345")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: _calculate_cost() with various models
# ─────────────────────────────────────────────────────────────────────────────


def test_calculate_cost_known_models():
    """Test cost calculation for models in the cost table."""
    from app.services.usage_tracking import _calculate_cost

    # GPT-4o: $2.5/M input, $10/M output
    cost = _calculate_cost("gpt-4o", 1000, 500)
    expected = (1000 * 2.5 + 500 * 10.0) / 1_000_000
    assert abs(cost - expected) < 0.0001, f"gpt-4o cost: {cost} != {expected}"

    # Claude Sonnet: $3/M input, $15/M output
    cost = _calculate_cost("claude-sonnet-4", 2000, 1000)
    expected = (2000 * 3.0 + 1000 * 15.0) / 1_000_000
    assert abs(cost - expected) < 0.0001, f"claude-sonnet-4 cost: {cost} != {expected}"

    # DeepSeek: $0.14/M input, $0.28/M output
    cost = _calculate_cost("deepseek-chat", 5000, 3000)
    expected = (5000 * 0.14 + 3000 * 0.28) / 1_000_000
    assert abs(cost - expected) < 0.0001, f"deepseek cost: {cost} != {expected}"


def test_calculate_cost_unknown_model():
    """Test cost calculation for unknown model uses default rate."""
    from app.services.usage_tracking import _calculate_cost

    # Default: $1/M input, $2/M output
    cost = _calculate_cost("unknown-model-xyz", 1000, 500)
    expected = (1000 * 1.0 + 500 * 2.0) / 1_000_000
    assert abs(cost - expected) < 0.0001, f"unknown model cost: {cost} != {expected}"


def test_calculate_cost_empty_model():
    """Test cost calculation for empty model returns 0."""
    from app.services.usage_tracking import _calculate_cost

    cost = _calculate_cost("", 1000, 500)
    assert cost == 0.0

    cost = _calculate_cost(None, 1000, 500)
    assert cost == 0.0


def test_calculate_cost_custom_rates():
    """Test custom cost rates override built-in table."""
    from app.services.usage_tracking import _calculate_cost

    custom_rates = {
        "openai/gpt-4o": {"input": 5.0, "output": 20.0},
    }

    # With custom rate
    cost = _calculate_cost("gpt-4o", 1000, 500, provider="openai", custom_rates=custom_rates)
    expected = (1000 * 5.0 + 500 * 20.0) / 1_000_000
    assert abs(cost - expected) < 0.0001, f"custom rate cost: {cost} != {expected}"

    # Without custom rate (should use built-in)
    cost_builtin = _calculate_cost("gpt-4o", 1000, 500, provider="openai", custom_rates=None)
    expected_builtin = (1000 * 2.5 + 500 * 10.0) / 1_000_000
    assert abs(cost_builtin - expected_builtin) < 0.0001


def test_calculate_cost_new_models():
    """Test that newly added models are covered."""
    from app.services.usage_tracking import _calculate_cost

    # These should NOT return default rate
    new_models = [
        ("gpt-4.1", 1000, 500),
        ("gpt-4.1-mini", 1000, 500),
        ("gpt-4.1-nano", 1000, 500),
        ("o3-mini", 1000, 500),
        ("claude-3.5-sonnet", 1000, 500),
        ("claude-3.5-haiku", 1000, 500),
        ("gemini-2.0-pro", 1000, 500),
        ("deepseek-coder", 1000, 500),
        ("qwen2.5", 1000, 500),
        ("llama-3.2", 1000, 500),
        ("command-r-plus", 1000, 500),
    ]

    default_cost = (1000 * 1.0 + 500 * 2.0) / 1_000_000

    for model, prompt, completion in new_models:
        cost = _calculate_cost(model, prompt, completion)
        assert cost != default_cost, f"{model} returned default cost — not in table"
