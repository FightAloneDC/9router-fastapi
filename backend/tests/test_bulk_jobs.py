"""Unit tests for provider bulk job workers."""

import asyncio
import uuid

from app.routers.providers import bulk_jobs
from app.services.bulk_connection_jobs import create_job, subscribe, unsubscribe


class FakeConnection:
    """Minimal provider connection used by the bulk worker test."""

    def __init__(self, connection_id: uuid.UUID) -> None:
        self.id = connection_id
        self.provider = "qoder"
        self.is_active = False


class FakeResult:
    """Minimal SQLAlchemy scalar result."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def scalar_one_or_none(self) -> FakeConnection:
        return self.connection


class FakeSession:
    """Minimal async session used by the bulk worker test."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def execute(self, _statement) -> FakeResult:
        return FakeResult(self.connection)

    async def commit(self) -> None:
        return None

    async def delete(self, _connection: FakeConnection) -> None:
        return None

    async def flush(self) -> None:
        return None


class FakeSessionContext:
    """Async context manager that supplies a fake database session."""

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *_args) -> None:
        return None


def test_enable_job_publishes_item_progress_and_done(monkeypatch) -> None:
    """An enable job activates its connection and publishes terminal events."""

    async def run() -> None:
        connection_id = uuid.uuid4()
        connection = FakeConnection(connection_id)
        session = FakeSession(connection)
        job = create_job("enable", "qoder", [str(connection_id)])
        queue = subscribe(job["jobId"])
        monkeypatch.setattr(
            bulk_jobs,
            "async_session",
            lambda: FakeSessionContext(session),
        )
        monkeypatch.setattr(
            bulk_jobs,
            "invalidate_connection_cache",
            lambda _provider_id: None,
        )

        await bulk_jobs.run_bulk_job(job["jobId"], [str(connection_id)])

        events = [queue.get_nowait() for _ in range(4)]
        unsubscribe(job["jobId"], queue)
        assert connection.is_active is True
        assert [event["type"] for event in events] == [
            "started",
            "item",
            "progress",
            "done",
        ]
        assert events[-1]["summary"] == {
            "total": 1,
            "passed": 1,
            "failed": 0,
        }

    asyncio.run(run())


def test_delete_job_invalidates_provider_connection_cache(monkeypatch) -> None:
    """A successful delete invalidates the provider routing cache."""
    async def run() -> None:
        async def renumber(*_args) -> None:
            return None

        connection_id = uuid.uuid4()
        connection = FakeConnection(connection_id)
        session = FakeSession(connection)
        job = create_job("delete", "qoder", [str(connection_id)])
        invalidated = []
        monkeypatch.setattr(
            bulk_jobs,
            "async_session",
            lambda: FakeSessionContext(session),
        )
        monkeypatch.setattr(
            bulk_jobs,
            "_renumber_provider_priorities",
            renumber,
        )
        monkeypatch.setattr(
            bulk_jobs,
            "invalidate_connection_cache",
            invalidated.append,
        )

        await bulk_jobs.run_bulk_job(job["jobId"], [str(connection_id)])

        assert invalidated == ["qoder"]

    asyncio.run(run())
