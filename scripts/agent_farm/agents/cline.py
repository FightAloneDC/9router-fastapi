"""Cline CLI plugin (OpenAI-compat via auth + runtime flags)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from ..common import KEY_ENV
from ._base import AgentPlugin


class ClineAgent(AgentPlugin):
    name = "cline"
    binary = "cline"
    supports_custom_openai = True
    needs_pty = True
    notes = "cline -P openai; PTY (no pipe)"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        key = os.environ.get(KEY_ENV, "")
        if not key:
            return {"ok": False, "error": f"missing {KEY_ENV}"}
        mid = models[0] if models else "mi/mistral-small-latest"
        cmd = [
            "cline",
            "auth",
            "openai",
            "--baseurl",
            base_url,
            "--apikey",
            key,
            "--modelid",
            mid,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "changed": ok,
            "exit": proc.returncode,
            "stderr": (proc.stderr or "")[-300:],
        }

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        work = work_dir.resolve()
        data_dir = work / ".cline-data"
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "cline",
                "--provider",
                "openai",
                "--key",
                api_key,
                "--model",
                model,
                "--cwd",
                str(work),
                "--data-dir",
                str(data_dir),
                "--json",
                "--auto-approve",
                "true",
                "--timeout",
                "90",
                prompt,
            ]
            if i > 0:
                cmd.extend(["--id", session_id])
            cmds.append(cmd)
        return cmds
