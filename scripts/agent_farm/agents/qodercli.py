"""Qoder CLI — -p/--print against 9Router model ids."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ._base import AgentPlugin


class QoderCliAgent(AgentPlugin):
    name = "qodercli"
    binary = "qodercli"
    supports_custom_openai = True
    notes = "qodercli -p -m; --session-id; extra OPENAI_*"

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
        del models
        return {
            "ok": True,
            "changed": False,
            "note": "runtime -m + OPENAI_*",
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
        sid = str(uuid.uuid5(uuid.NAMESPACE_URL, session_id))
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "qodercli",
                "-p",
                "-m",
                model,
                "-w",
                work,
                "--session-id",
                sid,
                "--permission-mode",
                "dont_ask",
                "--dangerously-skip-permissions",
                prompt,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
