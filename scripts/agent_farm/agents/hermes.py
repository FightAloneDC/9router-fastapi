"""Hermes agent plugin."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..common import (
    HERMES_ENV_FILE,
    HOME,
    KEY_ENV,
    atomic_write_text,
)
from ._base import AgentPlugin


class HermesAgent(AgentPlugin):
    name = "hermes"
    binary = "hermes"
    supports_custom_openai = True
    notes = "chat -q -Q; per-job --in + --continue"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".hermes" / "config.yaml"
        if not path.is_file():
            return {"ok": False, "error": f"missing {path}"}
        text = path.read_text()
        has_fast = (
            "name: FastRouter" in text
            or f"base_url: {base_url}" in text
            or f'base_url: "{base_url}"' in text
        )
        if has_fast:
            return {
                "ok": True,
                "path": str(path),
                "changed": False,
                "note": "FastRouter present; skip rewrite",
                "models_noted": len(models),
                "env_file": str(HERMES_ENV_FILE),
            }
        block = [
            "  - name: FastRouter",
            f"    base_url: {base_url}",
            f"    key_env: {KEY_ENV}",
            (
                f"    model: "
                f"{models[0] if models else 'deepseek-v4-flash'}"
            ),
            "    models:",
        ]
        for mid in models:
            block.append(f"      - {mid}")
        if re.search(r"^providers:\s*$", text, flags=re.M):
            new_text = text.rstrip() + "\n" + "\n".join(block) + "\n"
        else:
            new_text = (
                text.rstrip()
                + "\n\nproviders:\n"
                + "\n".join(block)
                + "\n"
            )
        atomic_write_text(path, new_text)
        return {"ok": True, "path": str(path), "changed": True}

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del api_key, session_id
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "hermes",
                "chat",
                "-Q",
                "-m",
                model,
                "--provider",
                "FastRouter",
                "--max-turns",
                "2",
                "--yolo",
                "--ignore-user-config",
                "--source",
                "tool",
                "--in",
                str(work_dir.resolve()),
                "-q",
                prompt,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
