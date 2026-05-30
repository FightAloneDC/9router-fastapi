"""In-memory active request tracker for real-time canvas updates.

Tracks in-flight proxy requests so the frontend canvas can animate
edges to providers that are currently handling requests.
"""

import time
from dataclasses import dataclass, field


@dataclass
class ActiveRequest:
    """A single in-flight request."""

    provider: str
    model: str
    started_at: float = field(default_factory=time.time)


# In-memory store — keyed by request_id
_active_requests: dict[str, ActiveRequest] = {}


def track_request_start(provider: str, model: str) -> str:
    """Start tracking an active request. Returns a unique request ID."""
    request_id = f"{provider}-{model}-{int(time.time() * 1000)}"
    _active_requests[request_id] = ActiveRequest(provider=provider, model=model)
    return request_id


def track_request_end(request_id: str) -> None:
    """Stop tracking a request."""
    _active_requests.pop(request_id, None)


def get_active_requests() -> list[dict[str, object]]:
    """Get all currently active requests."""
    return [
        {"provider": r.provider, "model": r.model, "startedAt": r.started_at}
        for r in _active_requests.values()
    ]
