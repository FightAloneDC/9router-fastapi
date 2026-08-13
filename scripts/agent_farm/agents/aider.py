"""Aider agent plugin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..common import DEFAULT_BASE_URL, HOME
from ._base import AgentPlugin

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from ..common import atomic_write_text


class AiderAgent(AgentPlugin):
    name = "aider"
    binary = "aider"
    supports_custom_openai = True
    notes = "flags --openai-api-base; weak multi-turn"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".aider.conf.yml"
        changed = False
        data: dict[str, Any] = {}
        if path.is_file() and yaml is not None:
            data = yaml.safe_load(path.read_text()) or {}
        if (
            "openai-api-base" not in data
            and "openai_api_base" not in data
        ):
            data["openai-api-base"] = base_url
            changed = True
        if changed and yaml is not None:
            atomic_write_text(
                path,
                yaml.safe_dump(
                    data,
                    sort_keys=False,
                    allow_unicode=True,
                ),
            )
        return {
            "ok": True,
            "path": str(path),
            "changed": changed,
            "note": "runtime uses --openai-api-base flags",
            "models_noted": len(models),
        }

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del work_dir, session_id
        base = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL)
        return [
            [
                "aider",
                "--model",
                f"openai/{model}",
                "--openai-api-base",
                base,
                "--openai-api-key",
                api_key,
                "--message",
                prompt,
                "--yes-always",
                "--no-git",
                "--no-show-model-warnings",
            ]
            for prompt in prompts
        ]
