"""Mimo / mimocode (opencode-family)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common import HOME, PROVIDER_ID, merge_opencode_provider
from ._base import AgentPlugin


class MimoAgent(AgentPlugin):
    name = "mimo"
    binary = "mimo"
    supports_custom_openai = True
    notes = "mimo run -m provider/model; --dir/--title"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        return merge_opencode_provider(
            HOME / ".config" / "mimocode" / "mimocode.json",
            base_url,
            models,
        )

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del api_key
        full = f"{PROVIDER_ID}/{model}"
        work = str(work_dir.resolve())
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "mimo",
                "run",
                "--dir",
                work,
                "--title",
                session_id,
                "-m",
                full,
                "--dangerously-skip-permissions",
                prompt,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
