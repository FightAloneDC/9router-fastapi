"""Usage tracking service — save request usage to usage_history and usage_daily tables."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_detail import RequestDetail
from app.models.usage import UsageDaily, UsageHistory

logger = logging.getLogger(__name__)

# Max JSON size before truncation (50 KB)
_MAX_JSON_SIZE = 50_000
_SENSITIVE_HEADER_KEYS = {"authorization", "x-api-key", "cookie", "token", "api-key"}


# ──────────────────────────────────────────────
# Cost rate table ($/M tokens)
# ──────────────────────────────────────────────

_COST_TABLE: list[tuple[str, float, float]] = [
    # (model_prefix, input_cost_per_million, output_cost_per_million)
    ("gpt-4o-mini", 0.15, 0.6),
    ("gpt-4o", 2.5, 10.0),
    ("gpt-4-turbo", 10.0, 30.0),
    ("gpt-4", 30.0, 60.0),
    ("gpt-3.5", 0.5, 1.5),
    ("o1-pro", 150.0, 600.0),
    ("o1", 15.0, 60.0),
    ("o3-pro", 200.0, 800.0),
    ("o3", 10.0, 40.0),
    ("o4-mini", 1.1, 4.4),
    ("claude-opus", 15.0, 75.0),
    ("claude-sonnet", 3.0, 15.0),
    ("claude-haiku", 0.8, 4.0),
    ("deepseek-r1", 0.55, 2.19),
    ("deepseek-v3", 0.27, 1.1),
    ("deepseek", 0.14, 0.28),
    ("gemini-2.5-pro", 1.25, 10.0),
    ("gemini-2.5-flash", 0.15, 0.6),
    ("gemini-2.0-flash", 0.1, 0.4),
    ("gemini-1.5-pro", 1.25, 5.0),
    ("gemini-1.5-flash", 0.075, 0.3),
    ("gemini", 0.0, 0.0),
    ("grok-3", 3.0, 15.0),
    ("grok-2", 2.0, 10.0),
    ("grok", 2.0, 10.0),
    ("llama-4", 0.2, 0.6),
    ("llama-3.3", 0.1, 0.1),
    ("llama-3.1-405b", 1.0, 1.0),
    ("llama-3", 0.05, 0.08),
    ("llama", 0.05, 0.08),
    ("mixtral", 0.25, 0.25),
    ("mistral-large", 2.0, 6.0),
    ("mistral", 0.25, 0.25),
    ("qwen-max", 1.6, 6.4),
    ("qwen-plus", 0.8, 2.0),
    ("qwen-turbo", 0.05, 0.2),
    ("qwen", 0.05, 0.2),
    ("gemma", 0.0, 0.0),
    ("command-r", 0.15, 0.6),
    ("cohere", 0.15, 0.6),
]


def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost based on model name and token counts."""
    if not model:
        return 0.0
    model_lower = model.lower()
    for prefix, input_rate, output_rate in _COST_TABLE:
        if prefix in model_lower:
            return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
    # Default rate
    return (prompt_tokens * 1.0 + completion_tokens * 2.0) / 1_000_000


def _get_date_key() -> str:
    """Get today's date key in YYYY-MM-DD format."""
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}-{now.day:02d}"


async def save_request_usage(
    db: AsyncSession,
    *,
    provider: str | None = None,
    model: str | None = None,
    connection_id: str | None = None,
    api_key: str | None = None,
    endpoint: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    status: str = "ok",
    tokens_json: dict | None = None,
    meta_json: dict | None = None,
) -> None:
    """Save a single request's usage data to usage_history and upsert usage_daily."""
    try:
        cost = _calculate_cost(model or "", prompt_tokens, completion_tokens)
        now = datetime.now(timezone.utc)

        # 1. Insert into usage_history
        row = UsageHistory(
            timestamp=now,
            provider=provider,
            model=model,
            connection_id=connection_id,
            api_key=api_key,
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            status=status,
            tokens=json.dumps(tokens_json or {}),
            meta=json.dumps(meta_json or {}),
        )
        db.add(row)

        # 2. Upsert usage_daily
        date_key = _get_date_key()
        result = await db.execute(
            select(UsageDaily).where(UsageDaily.date_key == date_key)
        )
        daily = result.scalar_one_or_none()

        if daily:
            day_data = json.loads(daily.data) if daily.data else {}
        else:
            day_data = {
                "requests": 0,
                "promptTokens": 0,
                "completionTokens": 0,
                "cost": 0,
                "byProvider": {},
                "byModel": {},
            }

        day_data["requests"] = day_data.get("requests", 0) + 1
        day_data["promptTokens"] = day_data.get("promptTokens", 0) + prompt_tokens
        day_data["completionTokens"] = day_data.get("completionTokens", 0) + completion_tokens
        day_data["cost"] = day_data.get("cost", 0) + cost

        # Aggregate by provider
        if provider:
            bp = day_data.setdefault("byProvider", {})
            p = bp.setdefault(provider, {"requests": 0, "promptTokens": 0, "completionTokens": 0, "cost": 0})
            p["requests"] += 1
            p["promptTokens"] += prompt_tokens
            p["completionTokens"] += completion_tokens
            p["cost"] += cost

        # Aggregate by model
        if model:
            bm = day_data.setdefault("byModel", {})
            model_key = f"{model}|{provider}" if provider else model
            m = bm.setdefault(model_key, {"requests": 0, "promptTokens": 0, "completionTokens": 0, "cost": 0, "rawModel": model, "provider": provider or ""})
            m["requests"] += 1
            m["promptTokens"] += prompt_tokens
            m["completionTokens"] += completion_tokens
            m["cost"] += cost

        if daily:
            daily.data = json.dumps(day_data)
        else:
            db.add(UsageDaily(date_key=date_key, data=json.dumps(day_data)))

        await db.commit()
    except Exception as e:
        logger.error(f"Failed to save usage stats: {e}")
        await db.rollback()


def _sanitize_headers(headers: dict | None) -> dict | None:
    """Strip sensitive headers (authorization, api-key, cookie, token)."""
    if not headers or not isinstance(headers, dict):
        return headers
    return {
        k: v for k, v in headers.items()
        if k.lower() not in _SENSITIVE_HEADER_KEYS
    }


def _truncate_json(obj, max_size: int = _MAX_JSON_SIZE) -> any:
    """Truncate a JSON-serializable object if it exceeds max_size bytes."""
    if obj is None:
        return None
    try:
        s = json.dumps(obj)
        if len(s) > max_size:
            preview = s[:200]
            return {"_truncated": True, "_originalSize": len(s), "_preview": preview}
    except (TypeError, ValueError):
        pass
    return obj


def _sanitize_payload(payload: dict | None, *, sanitize_headers: bool = False) -> dict | None:
    """Sanitize a request/response payload: optionally strip headers, truncate large payloads."""
    if payload is None or not isinstance(payload, dict):
        return _truncate_json(payload)
    result = dict(payload)
    if sanitize_headers and "headers" in result:
        result["headers"] = _sanitize_headers(result["headers"])
    return _truncate_json(result)


MAX_DETAILS = 500


async def cleanup_old_details(db: AsyncSession):
    """Delete oldest request_details if count exceeds MAX_DETAILS."""
    count_result = await db.execute(select(func.count(RequestDetail.id)))
    count = count_result.scalar() or 0
    if count > MAX_DETAILS:
        excess = count - MAX_DETAILS
        old_records = await db.execute(
            select(RequestDetail.id)
            .order_by(RequestDetail.timestamp.asc())
            .limit(excess)
        )
        old_ids = [r[0] for r in old_records.all()]
        if old_ids:
            await db.execute(
                delete(RequestDetail).where(RequestDetail.id.in_(old_ids))
            )
            await db.commit()


async def save_request_detail(
    db: AsyncSession,
    *,
    provider: str | None = None,
    model: str | None = None,
    connection_id: str | None = None,
    status: str = "ok",
    latency_ttft: int | None = None,
    latency_total: int | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost: float = 0.0,
    request_body: dict | None = None,
    provider_request_body: dict | None = None,
    provider_response_body: dict | None = None,
    response_body: dict | None = None,
) -> None:
    """Save full request/response payloads to the request_details table."""
    try:
        row = RequestDetail(
            provider=provider,
            model=model,
            connection_id=connection_id,
            status=status,
            latency_ttft=latency_ttft,
            latency_total=latency_total,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            request=json.dumps(_sanitize_payload(request_body, sanitize_headers=True)),
            provider_request=json.dumps(_sanitize_payload(provider_request_body)),
            provider_response=json.dumps(_sanitize_payload(provider_response_body)),
            response=json.dumps(_sanitize_payload(response_body)),
        )
        db.add(row)
        await db.commit()
        await cleanup_old_details(db)
    except Exception as e:
        logger.error(f"Failed to save request detail: {e}")
        await db.rollback()
