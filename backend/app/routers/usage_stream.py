"""SSE endpoint for real-time usage stats updates."""

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.routers.auth import get_current_user
from app.services.active_requests import get_active_requests

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
                active = get_active_requests()
                yield f"event: {event}\ndata: {json.dumps({'activeRequests': active})}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive with active requests
                active = get_active_requests()
                yield f"event: keepalive\ndata: {json.dumps({'activeRequests': active})}\n\n"
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
