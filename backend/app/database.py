"""Async SQLAlchemy engine, session factory, and dependency."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import suppress

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool.base import Pool

from app.config import settings


def _is_cancel_exc(exc: BaseException) -> bool:
    """True for asyncio/anyio cancellation (not app errors)."""
    if isinstance(exc, asyncio.CancelledError):
        return True
    return type(exc).__name__ == "CancelledError"


class IgnorePoolTerminateCancel(logging.Filter):
    """Belt-and-suspenders: drop pool terminate/cancel log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if (
            "terminating connection" not in msg
            and "closing connection" not in msg
        ):
            return True
        exc_info = record.exc_info
        if exc_info and exc_info[0] is not None:
            cls = exc_info[0]
            if "Cancelled" in getattr(cls, "__name__", ""):
                return False
            try:
                if issubclass(cls, asyncio.CancelledError):
                    return False
            except TypeError:
                pass
        if record.exc_text and "CancelledError" in record.exc_text:
            return False
        return True


def _quiet_pool_close_connection(
    self: Pool,
    connection: object,
    *,
    terminate: bool = False,
) -> None:
    """Like Pool._close_connection, but do not log CancelledError.

    Uvicorn cancels the request task after 200 OK when the client
    disconnects; asyncpg terminate then raises CancelledError and
    SQLAlchemy logs a full traceback. That is noise, not a failure.
    """
    self.logger.debug(
        "%s connection %r",
        "Hard-closing" if terminate else "Closing",
        connection,
    )
    try:
        if terminate:
            self._dialect.do_terminate(connection)
        else:
            self._dialect.do_close(connection)
    except BaseException as exc:
        if _is_cancel_exc(exc):
            raise
        self.logger.error(
            "Exception %s connection %r",
            "terminating" if terminate else "closing",
            connection,
            exc_info=True,
        )
        if not isinstance(exc, Exception):
            raise


def install_quiet_pool_terminate() -> None:
    """Patch SQLAlchemy pool + logging filters (idempotent)."""
    if getattr(Pool._close_connection, "_9router_quiet", False):
        return
    quiet = _quiet_pool_close_connection
    quiet._9router_quiet = True  # type: ignore[attr-defined]
    Pool._close_connection = quiet  # type: ignore[method-assign]

    filt = IgnorePoolTerminateCancel()
    for name in (
        "",
        "sqlalchemy.pool",
        "sqlalchemy.pool.base",
        "sqlalchemy.pool.QueuePool",
        "sqlalchemy.pool.AsyncAdaptedQueuePool",
    ):
        logging.getLogger(name).addFilter(filt)


install_quiet_pool_terminate()

# Async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# Async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def _shielded(awaitable):  # type: ignore[no-untyped-def]
    """Finish DB cleanup even if the request task is cancelled."""
    with suppress(Exception):
        await asyncio.shield(awaitable)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    session = async_session()
    try:
        yield session
        try:
            await asyncio.shield(session.commit())
        except asyncio.CancelledError:
            await _shielded(session.rollback())
            raise
    except asyncio.CancelledError:
        await _shielded(session.rollback())
        raise
    except Exception:
        await _shielded(session.rollback())
        raise
    finally:
        await _shielded(session.close())
