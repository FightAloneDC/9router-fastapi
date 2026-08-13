"""Zero CLI — wrapper may miss native binary; still farm-wired."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._base import AgentPlugin


class ZeroAgent(AgentPlugin):
    name = "zero"
    binary = "zero"
    supports_custom_openai = True
    notes = "zero -p; OPENAI_*; native binary may be missing"

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
            "note": "runtime OPENAI_*; wrapper may lack native bin",
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
        del api_key, session_id, work_dir
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = ["zero", "-p", prompt, "--model", model]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
