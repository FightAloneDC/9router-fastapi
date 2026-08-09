"""One-time backfill: move legacy quotaCache blobs into the
quota_cache table. Run inside the backend container:

    docker exec -i 9router-backend uv run python - \
        < tests/_backfill_quota_cache.py

Safe to re-run: rows already present in quota_cache are
skipped. Legacy blobs are left untouched.
"""

import asyncio
import json

from sqlalchemy import select

from app.database import async_session
from app.models.provider import ProviderConnection
from app.models.quota_cache import QuotaCache


async def main() -> None:
    migrated = skipped = missing = 0
    async with async_session() as db:
        result = await db.execute(select(ProviderConnection))
        for conn in result.scalars().all():
            try:
                data = json.loads(conn.data) if conn.data else {}
            except (json.JSONDecodeError, TypeError):
                continue
            cache_blob = data.get("quotaCache")
            if not isinstance(cache_blob, dict):
                missing += 1
                continue
            existing = await db.get(QuotaCache, conn.id)
            if existing is not None:
                skipped += 1
                continue
            row = QuotaCache(
                connection_id=conn.id,
                plan=cache_blob.get("plan"),
                quotas=json.dumps(
                    cache_blob.get("quotas", [])
                ),
                limit_reached=bool(
                    cache_blob.get("limit_reached")
                ),
            )
            fetched_at = cache_blob.get("fetchedAt")
            if fetched_at:
                from datetime import datetime
                try:
                    row.fetched_at = datetime.fromisoformat(
                        fetched_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            db.add(row)
            migrated += 1
        await db.commit()
    print(
        f"migrated={migrated} skipped={skipped} "
        f"no_blob={missing}"
    )


asyncio.run(main())
