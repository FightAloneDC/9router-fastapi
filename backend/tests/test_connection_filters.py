"""Unit tests for connection list filter predicates."""

from sqlalchemy import select

from app.models.provider import ProviderConnection
from app.routers.providers.connection_filters import (
    CONNECTED_TEST_STATUSES,
    ConnectionListFilters,
    build_connection_filter_clause,
)


def test_connected_aliases_constant():
    assert "connected" in CONNECTED_TEST_STATUSES
    assert "success" in CONNECTED_TEST_STATUSES
    assert "active" in CONNECTED_TEST_STATUSES


def test_base_clause_always_filters_provider():
    clause = build_connection_filter_clause(
        "qoder", ConnectionListFilters(),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "qoder" in sql


def test_q_adds_ilike_on_name_email_displayname():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(q="  alice@x.com  "),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "alice@x.com" in sql
    assert "ilike" in sql or " like " in sql


def test_is_active_and_auth_type():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(is_active=False, auth_type="oauth"),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "is_active" in sql
    assert "oauth" in sql


def test_test_status_connected_expands_aliases():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(test_status="connected"),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "connected" in sql
    assert "success" in sql or "active" in sql


def test_has_proxy_true_and_false():
    for has_proxy in (True, False):
        clause = build_connection_filter_clause(
            "qoder",
            ConnectionListFilters(has_proxy=has_proxy),
        )
        sql = str(
            select(ProviderConnection).where(clause).compile(
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
        assert "proxy_pool_id" in sql


def test_in_cooldown_false_compiles_not_exists():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(in_cooldown=False),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "not exists" in sql
    assert "modellock" in sql.replace("_", "")


def test_token_issue_and_cooldown_reference_json():
    clause = build_connection_filter_clause(
        "qoder",
        ConnectionListFilters(
            token_issue="any",
            in_cooldown=True,
        ),
    )
    sql = str(
        select(ProviderConnection).where(clause).compile(
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "expiresat" in sql.replace("_", "") or "expires" in sql
    assert (
        "modellock" in sql.replace("_", "")
        or "model_lock" in sql
        or "modellock" in sql
    )
