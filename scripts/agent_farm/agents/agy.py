"""Agy CLI — -p/--print."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._base import AgentPlugin


class AgyAgent(AgentPlugin):
    name = "agy"
    binary = "agy"
    supports_custom_openai = True
    notes = "agy -p --model; OPENAI_*"

    def extra_env(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
    ) -> dict[str, str]:
        del model
        return {
            "OPENAI_API_KEY": api_key,
            "OPENAI_BASE_URL": base_url,
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
            "note": "runtime -p --model + OPENAI_*",
            "base_url": base_url,
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
        work = str(work_dir.resolve())
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "agy",
                "-p",
                prompt,
                "--model",
                model,
                "--add-dir",
                work,
                "--dangerously-skip-permissions",
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
