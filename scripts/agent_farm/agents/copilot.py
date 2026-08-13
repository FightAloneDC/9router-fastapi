"""GitHub Copilot CLI — BYOK via COPILOT_PROVIDER_* env."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._base import AgentPlugin


class CopilotAgent(AgentPlugin):
    name = "copilot"
    binary = "copilot"
    supports_custom_openai = True
    notes = "copilot -p; COPILOT_PROVIDER_BASE_URL BYOK"

    def extra_env(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
    ) -> dict[str, str]:
        env = {
            "COPILOT_PROVIDER_BASE_URL": base_url,
            "COPILOT_PROVIDER_TYPE": "openai",
            "COPILOT_PROVIDER_API_KEY": api_key,
            "COPILOT_ALLOW_ALL": "1",
        }
        if model:
            env["COPILOT_MODEL"] = model
        return env

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        del models
        return {
            "ok": True,
            "changed": False,
            "note": "runtime COPILOT_PROVIDER_*",
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
        del api_key
        work = str(work_dir.resolve())
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "copilot",
                "-p",
                prompt,
                "--model",
                model,
                "--allow-all",
                "--silent",
                "-C",
                work,
                "--name",
                session_id,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
