"""OpenCode agent plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common import HOME, PROVIDER_ID, merge_opencode_provider
from ._base import AgentPlugin


class OpenCodeAgent(AgentPlugin):
    name = "opencode"
    binary = "opencode"
    supports_custom_openai = True
    notes = "opencode run -m provider/model; --dir/--title"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        return merge_opencode_provider(
            HOME / ".config" / "opencode" / "opencode.json",
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
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "opencode",
                "run",
                "--dir",
                str(work_dir),
                "--title",
                session_id,
                "-m",
                full,
                prompt,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
