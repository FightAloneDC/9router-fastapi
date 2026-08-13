"""Kiro CLI family: kiro-cli and kiro-cli-chat."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._base import AgentPlugin


class KiroChatAgent(AgentPlugin):
    supports_custom_openai = True
    notes = "chat --no-interactive --trust-all-tools"

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
            "note": "runtime chat --model + OPENAI_*",
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
            cmd = [
                self.binary,
                "chat",
                "--no-interactive",
                "--trust-all-tools",
                "--model",
                model,
                prompt,
            ]
            if i > 0:
                cmd.append("--resume")
            cmds.append(cmd)
        return cmds


def make_kiro(name: str, binary: str) -> KiroChatAgent:
    plugin = KiroChatAgent()
    plugin.name = name
    plugin.binary = binary
    plugin.notes = f"{binary} chat --no-interactive"
    return plugin
