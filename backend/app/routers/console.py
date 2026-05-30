"""Console log streaming endpoints."""

import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/console", tags=["console"])

# In-memory log buffer (last 500 entries)
_log_buffer: list[dict] = []
_log_subscribers: list[asyncio.Queue] = []


def add_log(level: str, message: str, source: str = "app"):
    """Called from middleware or logging handler."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "source": source,
    }
    _log_buffer.append(entry)
    if len(_log_buffer) > 500:
        _log_buffer.pop(0)
    for q in _log_subscribers:
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:
            pass


@router.get("/logs")
async def get_recent_logs(limit: int = 100):
    """Return recent log entries."""
    return {"logs": _log_buffer[-limit:]}


@router.websocket("/ws")
async def console_ws(websocket: WebSocket):
    """WebSocket endpoint for live log streaming."""
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _log_subscribers.append(queue)
    try:
        # Send recent history first
        for entry in _log_buffer[-50:]:
            await websocket.send_json(entry)
        # Stream live
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if queue in _log_subscribers:
            _log_subscribers.remove(queue)
