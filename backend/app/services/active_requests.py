"""In-memory active request tracker for real-time canvas updates.

Tracks in-flight proxy requests so the frontend canvas can animate
edges to providers that are currently handling requests.
Also maintains a ring buffer of recent completed requests and the
last error provider, matching the Node.js original pattern.
"""

import secrets
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class ActiveRequest:
    """A single in-flight request."""

    provider: str
    model: str
    started_at: float = field(default_factory=time.time)


# In-memory store — keyed by request_id
_active_requests: dict[str, ActiveRequest] = {}

# Ring buffer of recent completed requests (max 20)
_recent_requests: deque = deque(maxlen=20)

# Last provider that errored, with timestamp for expiry
_last_error_provider: dict[str, object] = {"provider": "", "ts": 0.0}

# Entries older than this are considered stale and pruned on access.
_MAX_ACTIVE_REQUEST_AGE = 600  # seconds
_ERROR_PROVIDER_TTL = 10  # seconds


def _notify_sse() -> None:
    """Fire SSE update event (late import to avoid circular dependency)."""
    try:
        from app.routers.usage_stream import notify_usage_update
        notify_usage_update()
    except ImportError:
        pass


def track_request_start(provider: str, model: str) -> str:
    """Start tracking an active request. Returns a unique request ID."""
    request_id = (
        f"{provider}-{model}-{int(time.time() * 1000)}"
        f"-{secrets.token_hex(4)}"
    )
    _active_requests[request_id] = ActiveRequest(
        provider=provider, model=model,
    )
    _notify_sse()
    return request_id


def track_request_end(
    request_id: str, status: str = "ok",
) -> None:
    """Stop tracking a request.

    If status is "error", record the provider as the last error provider
    so the frontend can show a red edge in Provider Topology.
    """
    req = _active_requests.pop(request_id, None)
    if req and status == "error":
        _last_error_provider["provider"] = req.provider.lower()
        _last_error_provider["ts"] = time.time()
    _notify_sse()


def push_recent_request(
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    status: str = "ok",
) -> None:
    """Push a completed request to the recent ring buffer.

    Called from save_request_tracking() after a request is saved to DB.
    """
    _recent_requests.append({
        "timestamp": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
        "model": model,
        "provider": provider,
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "status": status,
    })


def get_active_requests() -> list[dict[str, object]]:
    """Get all currently active requests.

    Stale entries (older than _MAX_ACTIVE_REQUEST_AGE) are pruned so the
    store cannot grow without bound if a track_request_end is ever missed
    (e.g. an exception between track_request_start and the end call).
    """
    now = time.time()
    stale = [
        rid for rid, r in _active_requests.items()
        if now - r.started_at > _MAX_ACTIVE_REQUEST_AGE
    ]
    for rid in stale:
        _active_requests.pop(rid, None)
    return [
        {"provider": r.provider, "model": r.model, "startedAt": r.started_at}
        for r in _active_requests.values()
    ]


def get_recent_requests() -> list[dict[str, object]]:
    """Get recent completed requests from the ring buffer (max 20)."""
    return list(_recent_requests)


def get_error_provider() -> str:
    """Get the last error provider if still within TTL."""
    if time.time() - _last_error_provider["ts"] < _ERROR_PROVIDER_TTL:
        return _last_error_provider["provider"]
    return ""
