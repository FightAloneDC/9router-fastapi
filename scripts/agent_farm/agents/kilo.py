"""Kilo agent plugin (opencode-family)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common import HOME, PROVIDER_ID, merge_opencode_provider
from ._base import AgentPlugin


class _KiloFamily(AgentPlugin):
    supports_custom_openai = True
    notes = "kilo run (opencode-family)"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        return merge_opencode_provider(
            HOME / ".config" / "kilo" / "kilo.jsonc",
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
                self.binary,
                "run",
                "--dir",
                work,
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


class KiloAgent(_KiloFamily):
    name = "kilo"
    binary = "kilo"
