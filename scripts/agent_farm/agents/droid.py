"""Factory Droid — customModels in ~/.factory/settings.json."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from ..common import HOME, KEY_ENV, load_json_config, atomic_write_json
from ._base import AgentPlugin


def droid_model_id(model: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", model).strip("-")
    return f"custom:fastapi-9router-{safe}"


class DroidAgent(AgentPlugin):
    name = "droid"
    binary = "droid"
    supports_custom_openai = True
    notes = "droid exec -m custom:fastapi-9router-*"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".factory" / "settings.json"
        if path.is_file():
            data = load_json_config(path)
        else:
            data = {}
        custom = list(data.get("customModels") or [])
        have = {
            str(x.get("model"))
            for x in custom
            if isinstance(x, dict)
        }
        key = os.environ.get(KEY_ENV, "")
        changed = False
        for mid in models:
            if mid in have:
                continue
            custom.append(
                {
                    "model": mid,
                    "id": droid_model_id(mid),
                    "baseUrl": base_url,
                    "apiKey": key,
                    "displayName": f"{mid} (FastAPI 9Router)",
                    "provider": "generic-chat-completion-api",
                    "noImageSupport": True,
                }
            )
            changed = True
        if changed:
            data["customModels"] = custom
            atomic_write_json(path, data)
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
        del api_key
        work = str(work_dir.resolve())
        mid = droid_model_id(model)
        sid = str(uuid.uuid5(uuid.NAMESPACE_URL, session_id))
        cmds: list[list[str]] = []
        for prompt in prompts:
            cmds.append(
                [
                    "droid",
                    "exec",
                    "-m",
                    mid,
                    "--cwd",
                    work,
                    "--session-id",
                    sid,
                    "--skip-permissions-unsafe",
                    prompt,
                ]
            )
        return cmds
