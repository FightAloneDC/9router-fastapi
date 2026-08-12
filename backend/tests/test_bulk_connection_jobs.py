"""Unit tests for bulk connection job store."""

import asyncio

from app.services import bulk_connection_jobs
from app.services.bulk_connection_jobs import (
    create_job,
    get_job,
    mark_done,
    publish,
    subscribe,
    unsubscribe,
)


def test_create_job_returns_id_and_total():
    job = create_job("test", "qoder", ["a", "b", "c"])
    assert job["action"] == "test"
    assert job["total"] == 3
    assert job["providerId"] == "qoder"
    assert get_job(job["jobId"]) is not None


def test_publish_reaches_subscriber():
    async def _run():
        job = create_job("enable", "qoder", ["a"])
        q = subscribe(job["jobId"])
        publish(job["jobId"], {"type": "started", "jobId": job["jobId"]})
        ev = await asyncio.wait_for(q.get(), timeout=1)
        unsubscribe(job["jobId"], q)
        assert ev["type"] == "started"

    asyncio.run(_run())


def test_cleanup_only_removes_expired_terminal_jobs(monkeypatch) -> None:
    """Expired pending jobs remain available while terminal jobs are evicted."""
    monkeypatch.setattr(bulk_connection_jobs, "_jobs", {})
    monkeypatch.setattr(bulk_connection_jobs.time, "time", lambda: 100.0)
    pending_job = create_job("enable", "qoder", ["pending"])
    done_job = create_job("disable", "qoder", ["done"])
    mark_done(done_job["jobId"], {"total": 1, "passed": 1, "failed": 0})

    monkeypatch.setattr(
        bulk_connection_jobs.time,
        "time",
        lambda: 100.0 + bulk_connection_jobs.JOB_TTL_SECONDS + 1,
    )
    create_job("test", "qoder", ["new"])

    assert get_job(pending_job["jobId"]) is not None
    assert get_job(done_job["jobId"]) is None
