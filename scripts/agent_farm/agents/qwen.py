"""Qwen Code agent plugin."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..common import HOME, KEY_ENV, atomic_write_json
from ._base import AgentPlugin


class QwenAgent(AgentPlugin):
    name = "qwen"
    binary = "qwen"
    supports_custom_openai = True
    notes = "qwen -p -m; --continue (project-scoped)"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".qwen" / "settings.json"
        if not path.is_file():
            return {"ok": False, "error": f"missing {path}"}
        data = json.loads(path.read_text())
        changed = False
        env = data.setdefault("env", {})
        if KEY_ENV not in env:
            key = os.environ.get(KEY_ENV, "")
            if key:
                env[KEY_ENV] = key
                changed = True
        openai_list = (
            data.setdefault("modelProviders", {}).setdefault("openai", [])
        )
        by_id = {
            str(x.get("id")): x
            for x in openai_list
            if isinstance(x, dict) and x.get("id")
        }
        for mid in models:
            if mid in by_id:
                entry = by_id[mid]
                if entry.get("baseUrl") != base_url:
                    entry["baseUrl"] = base_url
                    changed = True
                if entry.get("envKey") != KEY_ENV and KEY_ENV in env:
                    entry["envKey"] = KEY_ENV
                    changed = True
                continue
            openai_list.append(
                {
                    "id": mid,
                    "name": f"[9Router] {mid}",
                    "baseUrl": base_url,
                    "envKey": KEY_ENV,
                }
            )
            changed = True
        if changed:
            atomic_write_json(path, data)
        return {"ok": True, "path": str(path), "changed": changed}

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del api_key, session_id, work_dir
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = ["qwen", "-p", "-m", model, prompt]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
