"""SSE endpoint for real-time usage stats updates."""

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.routers.auth import get_current_user

router = APIRouter(tags=["usage-stream"])

# Simple in-memory event bus for usage updates
_subscribers: list[asyncio.Queue] = []


def notify_usage_update():
    """Called after each usage save to notify SSE clients."""
    for q in _subscribers:
        try:
            q.put_nowait("update")
        except asyncio.QueueFull:
            pass


async def _event_generator(queue: asyncio.Queue):
    """SSE generator that yields events from the queue."""
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25)
                yield f"event: {event}\ndata: {{}}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive ping
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/usage/stream")
async def usage_stream(
    _user=Depends(get_current_user),
):
    """SSE endpoint for real-time usage updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.append(queue)

    async def generate():
        try:
            async for event in _event_generator(queue):
                yield event
        finally:
            if queue in _subscribers:
                _subscribers.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
