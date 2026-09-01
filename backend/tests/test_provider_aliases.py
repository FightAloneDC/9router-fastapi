"""DB prefix overlay: missing row uses config."""

import asyncio
import json
from types import SimpleNamespace

from app.models.provider import ProviderNode
from app.models.provider_alias import ProviderAlias
from app.services.provider_aliases import (
    node_public_prefix,
    overlay_alias_to_id,
    overlay_alias_to_ids,
    overlay_id_to_alias,
    refresh_from_db,
    set_overrides,
)
from app.services.proxy import display_alias


def test_missing_db_keeps_config() -> None:
    set_overrides({})
    merged = overlay_id_to_alias({"openrouter": "openrouter"})
    assert merged["openrouter"] == "openrouter"
    routed = overlay_alias_to_id({"openrouter": "openrouter"})
    assert routed["openrouter"] == "openrouter"


def test_db_replaces_config_prefix() -> None:
    set_overrides({"openrouter": "or"})
    try:
        merged = overlay_id_to_alias({"openrouter": "openrouter"})
        assert merged["openrouter"] == "or"
        routed = overlay_alias_to_id({"openrouter": "openrouter"})
        assert routed["or"] == "openrouter"
        assert routed["openrouter"] == "openrouter"
        ids = overlay_alias_to_ids({"openrouter": ["openrouter"]})
        assert ids["or"] == ["openrouter"]
    finally:
        set_overrides({})


def test_node_public_prefix_reads_data_blob() -> None:
    assert node_public_prefix(None) == ""
    assert node_public_prefix("{") == ""
    assert node_public_prefix('{"baseUrl": "https://x"}') == ""
    assert node_public_prefix(
        json.dumps({"prefix": " farm-a ", "baseUrl": "https://x"}),
    ) == "farm-a"


class _Scalars:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class _Result:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _FakeDb:
    def __init__(self, alias_rows: list, node_rows: list) -> None:
        self._alias_rows = alias_rows
        self._node_rows = node_rows

    async def execute(self, stmt: object) -> _Result:
        entity = stmt.column_descriptions[0]["entity"]
        if entity is ProviderAlias:
            return _Result(self._alias_rows)
        if entity is ProviderNode:
            return _Result(self._node_rows)
        raise AssertionError(f"unexpected select {entity}")


def test_refresh_lists_custom_node_by_prefix() -> None:
    node_id = "openai-compatible-chat-abc"
    node = SimpleNamespace(
        id=node_id,
        data=json.dumps({"prefix": "farm-a", "baseUrl": "https://x"}),
    )
    db = _FakeDb([], [node])
    try:
        asyncio.run(refresh_from_db(db))
        assert display_alias(node_id) == "farm-a"
        routed = overlay_alias_to_id({})
        assert routed["farm-a"] == node_id
    finally:
        set_overrides({})
