"""Tests for provider connection priority renumbering."""

import asyncio
import uuid
from unittest.mock import MagicMock

from app.routers.providers.helpers import (
    _priorities_need_renumber,
    _renumber_provider_priorities,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


def test_renumber_assigns_unique_sequential_priorities():
    provider = "demo"
    rows = []
    for pri in (0, 0, 1, 1, 99):
        conn = MagicMock()
        conn.id = uuid.uuid4()
        conn.provider = provider
        conn.priority = pri
        rows.append(conn)

    db = MagicMock()

    async def _execute(stmt):
        return _FakeResult(rows)

    db.execute = _execute

    mapping = asyncio.run(_renumber_provider_priorities(db, provider))
    assert [c.priority for c in rows] == [0, 1, 2, 3, 4]
    assert list(mapping.values()) == [0, 1, 2, 3, 4]


def test_priorities_need_renumber_detects_gaps():
    provider = "demo"
    rows = [0, 1, 3]

    db = MagicMock()

    async def _execute(stmt):
        return _FakeResult(rows)

    db.execute = _execute

    assert asyncio.run(_priorities_need_renumber(db, provider)) is True


def test_priorities_need_renumber_ok_when_sequential():
    provider = "demo"
    rows = [0, 1, 2]

    db = MagicMock()

    async def _execute(stmt):
        return _FakeResult(rows)

    db.execute = _execute

    assert asyncio.run(_priorities_need_renumber(db, provider)) is False
