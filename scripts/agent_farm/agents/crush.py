"""Crush agent plugin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..common import (
    HOME,
    KEY_ENV,
    PROVIDER_ID,
    PROVIDER_NAME,
    atomic_write_json,
    load_json_config,
)
from ._base import AgentPlugin


def _crush_block(
    base_url: str,
    models: list[str],
    key: str,
) -> dict[str, Any]:
    return {
        "name": PROVIDER_NAME,
        "type": "openai-compat",
        "base_url": base_url,
        "api_key": key or f"${KEY_ENV}",
        "models": [{"id": m, "name": m} for m in models],
    }


def _merge_crush(
    path: Path,
    base_url: str,
    models: list[str],
    key: str,
) -> bool:
    if path.is_file():
        data = load_json_config(path)
    else:
        data = {"$schema": "https://charm.land/crush.json"}
    providers = data.setdefault("providers", {})
    block = providers.get(PROVIDER_ID)
    changed = False
    if block is None:
        providers[PROVIDER_ID] = _crush_block(base_url, models, key)
        atomic_write_json(path, data)
        return True
    if block.get("base_url") != base_url:
        block["base_url"] = base_url
        changed = True
    if block.get("type") != "openai-compat":
        block["type"] = "openai-compat"
        changed = True
    if not block.get("name"):
        block["name"] = PROVIDER_NAME
        changed = True
    existing = list(block.get("models") or [])
    have = {
        str(m.get("id") if isinstance(m, dict) else m)
        for m in existing
    }
    for mid in models:
        if mid not in have:
            existing.append({"id": mid, "name": mid})
            changed = True
    block["models"] = existing
    if changed:
        atomic_write_json(path, data)
    return changed


class CrushAgent(AgentPlugin):
    name = "crush"
    binary = "crush"
    supports_custom_openai = True
    notes = "crush run; --data-dir isolates sessions"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        key = os.environ.get(KEY_ENV, "")
        path = HOME / ".config" / "crush" / "crush.json"
        changed = _merge_crush(path, base_url, models, key)
        # Older farm wrote the same provider into the data dir;
        # Crush then sees fastapi-9router twice.
        data_path = HOME / ".local" / "share" / "crush" / "crush.json"
        if data_path.is_file():
            extra = load_json_config(data_path)
            providers = extra.get("providers") or {}
            if PROVIDER_ID in providers:
                del providers[PROVIDER_ID]
                extra["providers"] = providers
                atomic_write_json(data_path, extra)
                changed = True
        return {
            "ok": True,
            "path": str(path),
            "changed": changed,
        }

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del api_key, session_id
        work = work_dir.resolve()
        data_dir = work / ".crush-data"
        full = f"{PROVIDER_ID}/{model}"
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "crush",
                "run",
                "--quiet",
                "--cwd",
                str(work),
                "--data-dir",
                str(data_dir),
                "-m",
                full,
                prompt,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
