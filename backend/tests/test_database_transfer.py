"""Tests for FK-safe database export/import."""

from app.routers.providers.connection_filters import (
    ConnectionListFilters,
    build_export_filter_clause,
)
from app.services.database_transfer import (
    CONNECTIONS_TABLES,
    IMPORT_ORDER,
    ConnectionExportOptions,
    _providers_from_payload,
    export_options_to_filters_dict,
)


def test_import_order_places_proxy_pools_before_connections():
    pool_idx = IMPORT_ORDER.index("proxy_pools")
    conn_idx = IMPORT_ORDER.index("provider_connections")
    assert pool_idx < conn_idx


def test_connections_tables_include_catalog_and_quota():
    assert "provider_models" in CONNECTIONS_TABLES
    assert "quota_cache" in CONNECTIONS_TABLES
    assert "proxy_pools" in CONNECTIONS_TABLES


def test_export_filter_clause_without_providers():
    clause = build_export_filter_clause(
        ConnectionListFilters(is_active=True),
        None,
    )
    sql = str(clause).lower()
    assert "is_active" in sql


def test_export_options_to_filters_dict():
    options = ConnectionExportOptions(
        providers=["openai", "gemini"],
        filters=ConnectionListFilters(
            is_active=True,
            test_status="connected",
        ),
        health="healthy",
        include_catalog=True,
        include_quota=False,
    )
    payload = export_options_to_filters_dict(options)
    assert payload["providers"] == ["openai", "gemini"]
    assert payload["health"] == "healthy"
    assert payload["is_active"] is True
    assert payload["test_status"] == "connected"
    assert payload["include_quota"] is False


def test_providers_from_payload_prefers_filters():
    tables = {
        "provider_connections": [{"provider": "other"}],
    }
    filters = {"providers": ["openai"]}
    assert _providers_from_payload(tables, filters) == ["openai"]


def test_providers_from_payload_falls_back_to_connections():
    tables = {
        "provider_connections": [
            {"provider": "openai"},
            {"provider": "gemini"},
        ],
    }
    assert set(_providers_from_payload(tables, None)) == {"openai", "gemini"}
