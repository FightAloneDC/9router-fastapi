"""Cursor Agent family: agent, cursor-agent, cursor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..common import DEFAULT_BASE_URL
from ._base import AgentPlugin


class CursorAgent(AgentPlugin):
    name = "cursor-agent"
    binary = "cursor-agent"
    supports_custom_openai = True
    notes = "cursor-agent -p --endpoint --api-key"
    argv0: list[str] = ["cursor-agent"]

    def extra_env(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
    ) -> dict[str, str]:
        del model
        return {
            "CURSOR_API_KEY": api_key,
            "CURSOR_API_ENDPOINT": base_url,
        }

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        del models
        return {
            "ok": True,
            "changed": False,
            "note": "runtime --endpoint + CURSOR_API_*",
            "endpoint": base_url,
        }

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del session_id
        work = str(work_dir.resolve())
        endpoint = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL)
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                *self.argv0,
                "-p",
                prompt,
                "--api-key",
                api_key,
                "--endpoint",
                endpoint,
                "--model",
                model,
                "--force",
                "--trust",
                "--workspace",
                work,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds


def make_cursor(
    name: str,
    binary: str,
    argv0: list[str] | None = None,
) -> CursorAgent:
    plugin = CursorAgent()
    plugin.name = name
    plugin.binary = binary
    plugin.argv0 = argv0 or [binary]
    plugin.notes = f"{' '.join(plugin.argv0)} -p --endpoint"
    return plugin
