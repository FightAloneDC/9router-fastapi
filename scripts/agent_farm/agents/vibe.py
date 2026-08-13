"""Mistral Vibe CLI plugin."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..common import HOME, KEY_ENV, append_text, atomic_write_text
from ._base import AgentPlugin


class VibeAgent(AgentPlugin):
    name = "vibe"
    binary = "vibe"
    supports_custom_openai = True
    notes = "vibe -p; [[providers]] fastapi-9router"

    def extra_env(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
    ) -> dict[str, str]:
        del api_key, base_url
        env: dict[str, str] = {}
        if model:
            env["VIBE_ACTIVE_MODEL"] = model
        return env

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".vibe" / "config.toml"
        text = path.read_text() if path.is_file() else ""
        changed = False
        if 'name = "fastapi-9router"' not in text:
            key = os.environ.get(KEY_ENV, "")
            append_text(
                path,
                "\n[[providers]]\n"
                'name = "fastapi-9router"\n'
                f'api_base = "{base_url}"\n'
                f'api_key_env_var = "{KEY_ENV}"\n'
                + (f'api_key = "{key}"\n' if key else "")
                + 'api_style = "openai"\n'
                'backend = "generic"\n',
            )
            text = path.read_text()
            changed = True
        else:
            new_text, n = re.subn(
                r'(name = "fastapi-9router"\napi_base = ")[^"]*(")',
                rf"\g<1>{base_url}\2",
                text,
                count=1,
            )
            if n and new_text != text:
                atomic_write_text(path, new_text)
                text = new_text
                changed = True
        added: list[str] = []
        chunks: list[str] = []
        for mid in models:
            if f'name = "{mid}"' in text:
                continue
            chunks.append(
                "\n[[models]]\n"
                f'name = "{mid}"\n'
                'provider = "fastapi-9router"\n'
                f'alias = "{mid}"\n'
            )
            added.append(mid)
        if chunks:
            append_text(path, "".join(chunks))
            changed = True
        return {
            "ok": True,
            "path": str(path),
            "changed": changed,
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
        del api_key, session_id, model
        work = str(work_dir.resolve())
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "vibe",
                "-p",
                prompt,
                "--workdir",
                work,
                "--trust",
                "--auto-approve",
                "--output",
                "text",
                "--max-turns",
                "2",
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
