#!/usr/bin/env python3
"""
9Router FastAPI — Database Health Check Script
Tests Supabase PostgreSQL connection, verifies all tables exist,
checks schema, runs basic CRUD smoke tests, and reports status.

Usage:
    cd /home/mint/dev/9router-fastapi/backend
    uv run python ../scripts/test_database.py
"""

import asyncio
import sys
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

# ─── Config ───────────────────────────────────────────────────────────────────
#
# Default: local Docker PostgreSQL (dev environment)
# For Supabase production, set DATABASE_URL env var to your Supabase connection string.
# Note: Supabase direct connection is IPv6-only. If your VM lacks IPv6,
# use the Supavisor pooler (port 6543) or the IPv4 add-on.
#
# Loads from backend/.env if python-dotenv is available.
# Override via env var: DATABASE_URL=<your-url>

import os
from pathlib import Path

# Attempt to load .env from backend/ directory
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        pass  # python-dotenv not installed, rely on shell env

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    print("Either:")
    print("  1. Create backend/.env with DATABASE_URL=...")
    print("  2. Export DATABASE_URL in your shell")
    sys.exit(1)

# All tables expected by the app models
EXPECTED_TABLES = [
    "users",
    "api_keys",
    "settings",
    "kv",
    "provider_connections",
    "provider_nodes",
    "combos",
    "usage_history",
    "usage_daily",
    "mitm_config",
    "mitm_logs",
    "cli_tool_configs",
    "proxy_pools",
    "alembic_version",
]

# Expected columns per table (subset of critical columns)
EXPECTED_COLUMNS = {
    "users": ["id", "username", "hashed_password", "is_active", "created_at", "updated_at"],
    "api_keys": ["id", "key", "name", "is_active", "created_at"],
    "settings": ["id", "data", "created_at", "updated_at"],
    "kv": ["scope", "key", "value"],
    "provider_connections": ["id", "provider", "auth_type", "name", "priority", "is_active", "data", "created_at", "updated_at"],
    "provider_nodes": ["id", "type", "name", "data", "created_at", "updated_at"],
    "combos": ["id", "name", "kind", "models", "created_at", "updated_at"],
    "usage_history": ["id", "timestamp", "provider", "model", "prompt_tokens", "completion_tokens", "cost", "status"],
    "usage_daily": ["date_key", "data"],
    "mitm_config": ["id", "enabled", "port", "router_base_url", "tools_config", "updated_at"],
    "mitm_logs": ["id", "timestamp", "tool", "direction", "method", "url", "status_code"],
    "cli_tool_configs": ["id", "enabled", "config_data", "created_at", "updated_at"],
    "proxy_pools": ["id", "name", "proxy_url", "pool_type", "is_active", "test_status", "created_at", "updated_at"],
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

results = []


def log(status, category, message):
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "SKIP": "⏭️ "}.get(status, "  ")
    results.append((status, category, message))
    print(f"  {icon} [{category}] {message}")


def section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ─── Main Test Logic ─────────────────────────────────────────────────────────

async def run_tests():
    print("\n" + "=" * 60)
    print("  9Router FastAPI — Database Health Check")
    print("=" * 60)

    # ── 1. Parse URL ──────────────────────────────────────────────────────
    section("1. Connection String Validation")
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme in ("postgresql", "postgres"):
        log(PASS, "URL", f"Scheme: {parsed.scheme}")
    else:
        log(FAIL, "URL", f"Invalid scheme: {parsed.scheme}")

    log(PASS, "URL", f"Host: {parsed.hostname}")
    log(PASS, "URL", f"Port: {parsed.port}")
    log(PASS, "URL", f"Database: {parsed.path.lstrip('/')}")
    log(PASS, "URL", f"User: {parsed.username}")

    if "supabase" in (parsed.hostname or ""):
        log(PASS, "URL", "Supabase host detected")

    # ── 2. Import Dependencies ────────────────────────────────────────────
    section("2. Python Dependencies")
    try:
        import asyncpg
        log(PASS, "DEPS", f"asyncpg {asyncpg.__version__}")
    except ImportError:
        log(FAIL, "DEPS", "asyncpg not installed — run: uv add asyncpg")
        return

    try:
        import sqlalchemy
        log(PASS, "DEPS", f"SQLAlchemy {sqlalchemy.__version__}")
    except ImportError:
        log(FAIL, "DEPS", "sqlalchemy not installed")
        return

    # ── 3. Connection Test ────────────────────────────────────────────────
    section("3. Database Connection")
    conn = None
    try:
        conn = await asyncpg.connect(DATABASE_URL, timeout=15)
        log(PASS, "CONN", "Connected to Supabase PostgreSQL")

        # Server version
        version = await conn.fetchval("SELECT version()")
        log(PASS, "CONN", f"Server: {version[:80]}...")

        # Current database
        db_name = await conn.fetchval("SELECT current_database()")
        log(PASS, "CONN", f"Database: {db_name}")

        # Current user
        user = await conn.fetchval("SELECT current_user")
        log(PASS, "CONN", f"User: {user}")

        # Connection count
        count = await conn.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
        )
        log(PASS, "CONN", f"Active connections: {count}")

    except asyncpg.InvalidCatalogNameError:
        log(FAIL, "CONN", "Database does not exist")
        return
    except asyncpg.InvalidAuthorizationSpecificationError:
        log(FAIL, "CONN", "Authentication failed — check username/password")
        return
    except OSError as e:
        log(FAIL, "CONN", f"Network error: {e}")
        log(WARN, "CONN", "Supabase may require connection pooling on port 6543 (Supavisor)")
        # Try alternate port (Supavisor transaction mode)
        alt_url = DATABASE_URL.replace(":5432", ":6543")
        try:
            conn = await asyncpg.connect(alt_url, timeout=15)
            log(PASS, "CONN", "Connected via Supavisor pooler (port 6543)")
        except Exception as e2:
            log(FAIL, "CONN", f"Supavisor also failed: {e2}")
            return
    except asyncio.TimeoutError:
        log(FAIL, "CONN", "Connection timed out (15s)")
        return
    except Exception as e:
        log(FAIL, "CONN", f"Unexpected error: {type(e).__name__}: {e}")
        return

    # ── 4. Table Existence ────────────────────────────────────────────────
    section("4. Table Existence Check")
    existing_tables = set()
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    )
    for row in rows:
        existing_tables.add(row["table_name"])

    missing_tables = []
    for table in EXPECTED_TABLES:
        if table in existing_tables:
            log(PASS, "TABLE", f"{table}")
        else:
            log(FAIL, "TABLE", f"{table} — MISSING")
            missing_tables.append(table)

    extra_tables = existing_tables - set(EXPECTED_TABLES)
    if extra_tables:
        for t in sorted(extra_tables):
            log(WARN, "TABLE", f"{t} — unexpected (not in models)")

    # ── 5. Column Validation ──────────────────────────────────────────────
    section("5. Column Validation")
    for table, expected_cols in EXPECTED_COLUMNS.items():
        if table in missing_tables:
            log(SKIP, "COLS", f"{table} — skipped (table missing)")
            continue

        col_rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = $1",
            table,
        )
        actual_cols = {row["column_name"] for row in col_rows}

        for col in expected_cols:
            if col in actual_cols:
                log(PASS, "COLS", f"{table}.{col}")
            else:
                log(FAIL, "COLS", f"{table}.{col} — MISSING")

    # ── 6. Index Check ────────────────────────────────────────────────────
    section("6. Index Check")
    index_rows = await conn.fetch(
        "SELECT indexname, tablename FROM pg_indexes "
        "WHERE schemaname = 'public' ORDER BY tablename, indexname"
    )
    index_count = len(index_rows)
    log(PASS, "INDEX", f"Found {index_count} indexes")

    # Group by table
    from collections import defaultdict
    indexes_by_table = defaultdict(list)
    for row in index_rows:
        indexes_by_table[row["tablename"]].append(row["indexname"])

    for table in sorted(indexes_by_table):
        idx_list = indexes_by_table[table]
        log(PASS, "INDEX", f"{table}: {', '.join(idx_list)}")

    # ── 7. Row Counts ─────────────────────────────────────────────────────
    section("7. Row Counts")
    for table in sorted(existing_tables):
        try:
            count = await conn.fetchval(f'SELECT count(*) FROM "{table}"')
            log(PASS, "ROWS", f"{table}: {count} rows")
        except Exception as e:
            log(WARN, "ROWS", f"{table}: count failed — {e}")

    # ── 8. CRUD Smoke Test ────────────────────────────────────────────────
    section("8. CRUD Smoke Tests")
    test_id = uuid.uuid4()
    test_username = f"_healthcheck_{uuid.uuid4().hex[:8]}"

    # INSERT
    try:
        await conn.execute(
            "INSERT INTO users (id, username, hashed_password, is_active) "
            "VALUES ($1, $2, $3, $4)",
            test_id, test_username, "test_hash", True,
        )
        log(PASS, "CRUD", f"INSERT into users — id={test_id}")
    except Exception as e:
        log(FAIL, "CRUD", f"INSERT into users failed: {e}")

    # SELECT
    try:
        row = await conn.fetchrow(
            "SELECT id, username, is_active FROM users WHERE id = $1", test_id
        )
        if row and row["username"] == test_username:
            log(PASS, "CRUD", f"SELECT from users — username={row['username']}")
        else:
            log(FAIL, "CRUD", "SELECT from users — row not found or mismatch")
    except Exception as e:
        log(FAIL, "CRUD", f"SELECT from users failed: {e}")

    # UPDATE
    try:
        await conn.execute(
            "UPDATE users SET is_active = $1 WHERE id = $2", False, test_id
        )
        updated = await conn.fetchval(
            "SELECT is_active FROM users WHERE id = $1", test_id
        )
        if updated is False:
            log(PASS, "CRUD", "UPDATE users — is_active set to False")
        else:
            log(FAIL, "CRUD", f"UPDATE users — expected False, got {updated}")
    except Exception as e:
        log(FAIL, "CRUD", f"UPDATE users failed: {e}")

    # DELETE
    try:
        await conn.execute("DELETE FROM users WHERE id = $1", test_id)
        remaining = await conn.fetchval(
            "SELECT count(*) FROM users WHERE id = $1", test_id
        )
        if remaining == 0:
            log(PASS, "CRUD", "DELETE from users — row removed")
        else:
            log(FAIL, "CRUD", f"DELETE from users — {remaining} rows remain")
    except Exception as e:
        log(FAIL, "CRUD", f"DELETE from users failed: {e}")

    # ── 9. Transaction Test ───────────────────────────────────────────────
    section("9. Transaction Test")
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO settings (id, data) VALUES (999, $1) "
                "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data",
                json.dumps({"_healthcheck": True}),
            )
        verify = await conn.fetchval("SELECT data FROM settings WHERE id = 999")
        if verify and "_healthcheck" in verify:
            log(PASS, "TXN", "Transaction + upsert works")
            # Cleanup
            await conn.execute("DELETE FROM settings WHERE id = 999")
        else:
            log(WARN, "TXN", f"Transaction committed but data unexpected: {verify}")
    except Exception as e:
        log(FAIL, "TXN", f"Transaction failed: {e}")

    # ── 10. UUID Extension ────────────────────────────────────────────────
    section("10. PostgreSQL Extensions")
    ext_rows = await conn.fetch(
        "SELECT extname, extversion FROM pg_extension ORDER BY extname"
    )
    for row in ext_rows:
        log(PASS, "EXT", f"{row['extname']} v{row['extversion']}")

    # Check uuid-ossp specifically
    has_uuid = any(r["extname"] == "uuid-ossp" for r in ext_rows)
    if has_uuid:
        log(PASS, "EXT", "uuid-ossp available for uuid_generate_v4()")
    else:
        log(WARN, "EXT", "uuid-ossp not installed (app uses Python uuid4, so this is OK)")

    # ── 11. Permissions ───────────────────────────────────────────────────
    section("11. Permission Check")
    try:
        can_create = await conn.fetchval(
            "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"
        )
        log(PASS if can_create else WARN, "PERM", f"CREATE privilege: {can_create}")
    except Exception as e:
        log(WARN, "PERM", f"Could not check CREATE privilege: {e}")

    # ── Close ─────────────────────────────────────────────────────────────
    await conn.close()

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    counts = {PASS: 0, FAIL: 0, WARN: 0, SKIP: 0}
    for status, _, _ in results:
        counts[status] += 1

    print(f"  ✅ Passed:  {counts[PASS]}")
    print(f"  ❌ Failed:  {counts[FAIL]}")
    print(f"  ⚠️  Warnings: {counts[WARN]}")
    print(f"  ⏭️  Skipped: {counts[SKIP]}")
    print()

    if counts[FAIL] == 0:
        print("  🎉 Database is READY — all critical checks passed!")
    else:
        print("  🔥 Database has FAILURES — fix the issues above before running the app.")
        print("     Run: cd backend && uv run alembic upgrade head")

    print()
    return counts[FAIL] == 0


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        ok = asyncio.run(run_tests())
        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        print("\n  Aborted.")
        sys.exit(130)
