"""Unit tests for bulk connection job store."""

import asyncio

from app.services.bulk_connection_jobs import (
    create_job,
    get_job,
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
