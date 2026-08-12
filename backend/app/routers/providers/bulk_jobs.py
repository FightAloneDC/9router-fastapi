"""Bulk provider connection actions with progress WebSocket updates."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_202_ACCEPTED

from app.database import async_session, get_db
from app.models.provider import ProviderConnection
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.constants import normalize_models_list
from app.routers.providers.helpers import _renumber_provider_priorities
from app.routers.providers.testing import _test_provider_connection
from app.services.auth import decode_access_token
from app.services.bulk_connection_jobs import (
    create_job,
    get_job,
    mark_done,
    mark_error,
    publish,
    subscribe,
    unsubscribe,
)
from app.services.proxy import invalidate_connection_cache

_background_tasks: set[asyncio.Task[None]] = set()


class BulkJobCreate(BaseModel):
    """Request to run one action against provider connections."""

    action: Literal["enable", "disable", "test", "delete"]
    ids: list[uuid.UUID]


def _progress_event(
    job_id: str,
    completed: int,
    total: int,
    passed: int,
    failed: int,
) -> dict:
    """Build a progress event for a bulk job."""
    return {
        "type": "progress",
        "jobId": job_id,
        "completed": completed,
        "total": total,
        "passed": passed,
        "failed": failed,
    }


def _update_test_data(
    conn: ProviderConnection,
    test_result: dict,
) -> str:
    """Persist a provider test result in its data JSON blob."""
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    valid = test_result["valid"]
    test_status = "connected" if valid else "error"
    data["testStatus"] = test_status
    if not valid and test_result.get("error"):
        data["lastError"] = test_result["error"]
        data["lastErrorAt"] = datetime.now(timezone.utc).isoformat()
    if valid and test_result.get("models"):
        data["models"] = normalize_models_list(test_result["models"])
    conn.data = json.dumps(data)
    return test_status


async def _run_test_item(
    connection_id: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Test and persist one connection with an isolated database session."""
    async with semaphore:
        async with async_session() as db:
            result = await db.execute(
                select(ProviderConnection).where(
                    ProviderConnection.id == uuid.UUID(connection_id)
                )
            )
            conn = result.scalar_one_or_none()
            if conn is None:
                return {
                    "connectionId": connection_id,
                    "ok": False,
                    "testStatus": "error",
                    "error": "Provider connection not found",
                }

            try:
                test_result = await _test_provider_connection(conn, db)
                test_status = _update_test_data(conn, test_result)
                await db.commit()
                return {
                    "connectionId": connection_id,
                    "ok": test_result["valid"],
                    "testStatus": test_status,
                    "error": test_result.get("error"),
                }
            except Exception as exc:
                await db.rollback()
                return {
                    "connectionId": connection_id,
                    "ok": False,
                    "testStatus": "error",
                    "error": str(exc)[:200],
                }


async def _run_test_job(
    job_id: str,
    connection_ids: list[str],
    total: int,
) -> tuple[int, int]:
    """Run connection tests with at most three upstream requests at once."""
    semaphore = asyncio.Semaphore(3)
    tasks = [
        _run_test_item(connection_id, semaphore) for connection_id in connection_ids
    ]
    passed = 0
    failed = 0
    for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
        item = await task
        if item["ok"]:
            passed += 1
        else:
            failed += 1
        publish(
            job_id,
            {
                "type": "item",
                "jobId": job_id,
                **item,
            },
        )
        publish(
            job_id,
            _progress_event(job_id, completed, total, passed, failed),
        )
    return passed, failed


async def _run_standard_job(
    job_id: str,
    action: str,
    provider_id: str,
    connection_ids: list[str],
    total: int,
) -> tuple[int, int]:
    """Run enable, disable, or delete actions in one job database session."""
    passed = 0
    failed = 0
    deleted = False
    active_changed = False
    async with async_session() as db:
        for completed, connection_id in enumerate(connection_ids, start=1):
            item = {
                "type": "item",
                "jobId": job_id,
                "connectionId": connection_id,
            }
            try:
                result = await db.execute(
                    select(ProviderConnection).where(
                        ProviderConnection.id == uuid.UUID(connection_id)
                    )
                )
                conn = result.scalar_one_or_none()
                if conn is None:
                    raise ValueError("Provider connection not found")

                if action == "delete":
                    await db.delete(conn)
                    deleted = True
                else:
                    conn.is_active = action == "enable"
                    item["isActive"] = conn.is_active
                    active_changed = True
                passed += 1
                item["ok"] = True
            except Exception as exc:
                failed += 1
                item["ok"] = False
                item["error"] = str(exc)[:200]

            publish(job_id, item)
            publish(
                job_id,
                _progress_event(job_id, completed, total, passed, failed),
            )

        if deleted:
            await db.flush()
            await _renumber_provider_priorities(db, provider_id)
        await db.commit()
    if active_changed or deleted:
        invalidate_connection_cache(provider_id)
    return passed, failed


async def run_bulk_job(job_id: str, connection_ids: list[str]) -> None:
    """Run a bulk job and publish lifecycle events to its subscribers."""
    job = get_job(job_id)
    if job is None:
        return

    action = job["action"]
    total = job["total"]
    provider_id = job["providerId"]
    publish(job_id, {"type": "started", **job})

    try:
        if action == "test":
            passed, failed = await _run_test_job(
                job_id,
                connection_ids,
                total,
            )
        else:
            passed, failed = await _run_standard_job(
                job_id,
                action,
                provider_id,
                connection_ids,
                total,
            )
    except Exception as exc:
        mark_error(job_id, str(exc)[:200])
        return

    mark_done(
        job_id,
        {
            "total": total,
            "passed": passed,
            "failed": failed,
        },
    )


@router.post(
    "/providers/by-provider/{provider_id}/connections/bulk-jobs",
    status_code=HTTP_202_ACCEPTED,
)
async def create_bulk_job(
    provider_id: str,
    body: BulkJobCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """Create and start an asynchronous bulk connection action."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="'ids' must not be empty")

    rows = (
        await db.execute(
            select(ProviderConnection.id, ProviderConnection.provider).where(
                ProviderConnection.id.in_(body.ids)
            )
        )
    ).all()
    if len(rows) != len(body.ids):
        raise HTTPException(
            status_code=400,
            detail="One or more connections not found",
        )
    if any(row.provider != provider_id for row in rows):
        raise HTTPException(
            status_code=400,
            detail="Connection does not belong to provider",
        )

    job = create_job(body.action, provider_id, [str(item) for item in body.ids])
    task = asyncio.create_task(
        run_bulk_job(job["jobId"], [str(item) for item in body.ids])
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return job


@router.websocket("/providers/bulk-jobs/ws")
async def bulk_jobs_ws(websocket: WebSocket) -> None:
    """Stream lifecycle and progress events for one bulk connection job."""
    token = websocket.query_params.get("token")
    job_id = websocket.query_params.get("jobId")
    if not token or decode_access_token(token) is None or not job_id:
        await websocket.close(code=1008)
        return

    job = get_job(job_id)
    if job is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        queue = subscribe(job_id)
    except KeyError:
        await websocket.close(code=1008)
        return

    try:
        await websocket.send_json({"type": "status", **job})
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["type"] in {"done", "error"}:
                return
    except WebSocketDisconnect:
        return
    finally:
        unsubscribe(job_id, queue)
