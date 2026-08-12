"""In-memory bulk connection job store with pub/sub queues."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Literal

BulkAction = Literal["enable", "disable", "test", "delete"]

JOB_TTL_SECONDS = 600
_QUEUE_MAXSIZE = 100

_jobs: dict[str, dict] = {}


def _cleanup_expired() -> None:
    now = time.time()
    expired = [
        job_id
        for job_id, job in _jobs.items()
        if now - job["createdAt"] > JOB_TTL_SECONDS
    ]
    for job_id in expired:
        _jobs.pop(job_id, None)


def _job_snapshot(job: dict) -> dict:
    out = {
        "jobId": job["jobId"],
        "action": job["action"],
        "total": job["total"],
        "providerId": job["providerId"],
        "status": job["status"],
        "createdAt": job["createdAt"],
    }
    if "summary" in job:
        out["summary"] = job["summary"]
    if "message" in job:
        out["message"] = job["message"]
    return out


def create_job(
    action: str,
    provider_id: str,
    ids: list[str],
) -> dict:
    _cleanup_expired()
    job_id = uuid.uuid4().hex
    job = {
        "jobId": job_id,
        "action": action,
        "providerId": provider_id,
        "ids": list(ids),
        "total": len(ids),
        "status": "pending",
        "createdAt": time.time(),
        "subscribers": [],
        "events": [],
    }
    _jobs[job_id] = job
    return {
        "jobId": job_id,
        "action": action,
        "total": len(ids),
        "providerId": provider_id,
    }


def get_job(job_id: str) -> dict | None:
    _cleanup_expired()
    job = _jobs.get(job_id)
    if job is None:
        return None
    return _job_snapshot(job)


def subscribe(job_id: str) -> asyncio.Queue:
    job = _jobs.get(job_id)
    if job is None:
        raise KeyError(f"Unknown job: {job_id}")
    queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    job["subscribers"].append(queue)
    for event in job["events"]:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            break
    return queue


def unsubscribe(job_id: str, queue: asyncio.Queue) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    try:
        job["subscribers"].remove(queue)
    except ValueError:
        pass


def publish(job_id: str, event: dict) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    job["events"].append(event)
    for queue in list(job["subscribers"]):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def mark_done(job_id: str, summary: dict) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    job["status"] = "done"
    job["summary"] = summary
    publish(
        job_id,
        {"type": "done", "jobId": job_id, "summary": summary},
    )


def mark_error(job_id: str, message: str) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    job["status"] = "error"
    job["message"] = message
    publish(
        job_id,
        {"type": "error", "jobId": job_id, "message": message},
    )
