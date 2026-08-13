"""Pi agent plugin."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..common import HOME, KEY_ENV, PROVIDER_ID, atomic_write_json
from ._base import AgentPlugin


class PiAgent(AgentPlugin):
    name = "pi"
    binary = "pi"
    supports_custom_openai = True
    notes = "pi -p --session-id unique"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".pi" / "agent" / "models.json"
        if path.is_file():
            data = json.loads(path.read_text())
        else:
            data = {"providers": {}}
        providers = data.setdefault("providers", {})
        block = providers.get(PROVIDER_ID)
        changed = False
        if block is None:
            providers[PROVIDER_ID] = {
                "baseUrl": base_url,
                "api": "openai-completions",
                "apiKey": f"${{{KEY_ENV}}}",
                "models": [
                    {
                        "id": m,
                        "name": m,
                        "reasoning": True,
                        "input": ["text"],
                    }
                    for m in models
                ],
            }
            key = os.environ.get(KEY_ENV, "")
            if key:
                providers[PROVIDER_ID]["apiKey"] = key
            changed = True
        else:
            if block.get("baseUrl") != base_url:
                block["baseUrl"] = base_url
                changed = True
            existing = list(block.get("models") or [])
            have = {
                str(m.get("id"))
                for m in existing
                if isinstance(m, dict) and m.get("id")
            }
            for mid in models:
                if mid not in have:
                    existing.append(
                        {
                            "id": mid,
                            "name": mid,
                            "reasoning": True,
                            "input": ["text"],
                        }
                    )
                    changed = True
            block["models"] = existing
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
        del work_dir
        return [
            [
                "pi",
                "-p",
                "--session-id",
                session_id,
                "--provider",
                PROVIDER_ID,
                "--model",
                model,
                "--api-key",
                api_key,
                prompt,
            ]
            for prompt in prompts
        ]
