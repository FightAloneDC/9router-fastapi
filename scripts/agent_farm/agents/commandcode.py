"""Command Code family: cmd, cmdc, command-code, commandcode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common import HOME, atomic_write_json, load_json_config
from ._base import AgentPlugin


class CommandCodeAgent(AgentPlugin):
    supports_custom_openai = True
    notes = "-p -m; OPENAI_BASE_URL + --yolo"

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
            "OPENAI_API_BASE": base_url,
        }

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        del base_url
        path = HOME / ".commandcode" / "config.json"
        if path.is_file():
            data = load_json_config(path)
        else:
            data = {}
        changed = False
        if models and data.get("model") != models[0]:
            data["model"] = models[0]
            changed = True
        if changed:
            atomic_write_json(path, data)
        return {
            "ok": True,
            "path": str(path),
            "changed": changed,
            "note": "runtime OPENAI_BASE_URL",
        }

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del api_key, work_dir
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                self.binary,
                "-p",
                prompt,
                "-m",
                model,
                "--yolo",
                "--skip-onboarding",
                "--trust",
                "--name",
                session_id,
                "--max-turns",
                "4",
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds


def make_commandcode(name: str, binary: str) -> CommandCodeAgent:
    plugin = CommandCodeAgent()
    plugin.name = name
    plugin.binary = binary
    plugin.notes = f"{binary} -p -m; OPENAI_BASE_URL"
    return plugin
