"""WebSocket endpoint for real-time usage stats updates."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.active_requests import (
    get_active_requests,
    get_error_provider,
    get_recent_requests,
)
from app.services.auth import decode_access_token

router = APIRouter(tags=["usage-stream"])

# In-memory fan-out for connected usage WS clients
_subscribers: list[asyncio.Queue] = []


def notify_usage_update() -> None:
    """Wake all usage WS clients after a usage save / active-request change."""
    for q in _subscribers:
        try:
            q.put_nowait("update")
        except asyncio.QueueFull:
            pass


def _build_payload() -> dict:
    """Real-time usage fields for the overview page."""
    return {
        "activeRequests": get_active_requests(),
        "recentRequests": get_recent_requests(),
        "errorProvider": get_error_provider(),
    }


@router.websocket("/usage/ws")
async def usage_ws(websocket: WebSocket) -> None:
    """Live usage updates over WebSocket (replaces SSE /usage/stream)."""
    token = websocket.query_params.get("token")
    if not token or decode_access_token(token) is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.append(queue)

    try:
        await websocket.send_json(_build_payload())
        while True:
            try:
                await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                pass
            await websocket.send_json(_build_payload())
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)
