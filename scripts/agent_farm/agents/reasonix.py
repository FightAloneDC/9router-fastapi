"""Reasonix plugin — [[providers]] merge into ~/.reasonix/config.toml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..common import HOME, KEY_ENV, append_text
from ._base import AgentPlugin


def reasonix_provider_name(model: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", model).strip("-")
    return f"fastapi-9router-{safe}"


class ReasonixAgent(AgentPlugin):
    name = "reasonix"
    binary = "reasonix"
    supports_custom_openai = True
    notes = "reasonix -p --model fastapi-9router-*"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".reasonix" / "config.toml"
        text = path.read_text() if path.is_file() else ""
        added: list[str] = []
        chunks: list[str] = []
        for mid in models:
            name = reasonix_provider_name(mid)
            if f'name        = "{name}"' in text or (
                f'name = "{name}"' in text
            ):
                continue
            chunks.append(
                "\n[[providers]]\n"
                f'name        = "{name}"\n'
                'kind        = "openai"\n'
                f'base_url    = "{base_url}"\n'
                f'model       = "{mid}"\n'
                f'api_key_env = "{KEY_ENV}"\n'
            )
            added.append(name)
        if chunks:
            append_text(path, "".join(chunks))
        return {
            "ok": True,
            "path": str(path),
            "changed": bool(added),
            "added": added,
        }

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del api_key, session_id
        work = str(work_dir.resolve())
        name = reasonix_provider_name(model)
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "reasonix",
                "-p",
                "--model",
                name,
                "--output-format",
                "text",
                "--permission-mode",
                "dontAsk",
                "--add-dir",
                work,
                prompt,
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
