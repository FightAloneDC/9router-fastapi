"""Grok CLI plugin (headless -p against custom OpenAI models)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from ..common import HOME, KEY_ENV, append_text
from ._base import AgentPlugin


def grok_model_key(model: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", model).strip("-")
    return f"fastapi-9router-{safe}"


class GrokAgent(AgentPlugin):
    name = "grok"
    binary = "grok"
    supports_custom_openai = True
    notes = "grok -p; [model.fastapi-9router-*] in config.toml"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".grok" / "config.toml"
        text = path.read_text() if path.is_file() else ""
        added: list[str] = []
        chunks: list[str] = []
        for mid in models:
            key = grok_model_key(mid)
            header = f"[model.{key}]"
            if header in text:
                continue
            chunks.append(
                f"\n{header}\n"
                f'base_url = "{base_url}"\n'
                f'env_key = "{KEY_ENV}"\n'
                f'model = "{mid}"\n'
                f'name = "{mid} (FastAPI 9Router)"\n'
            )
            added.append(key)
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
        del api_key
        work = str(work_dir.resolve())
        key = grok_model_key(model)
        sid = str(uuid.uuid5(uuid.NAMESPACE_URL, session_id))
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = [
                "grok",
                "-p",
                prompt,
                "-m",
                key,
                "--cwd",
                work,
                "--output-format",
                "plain",
                "--yolo",
                "--max-turns",
                "2",
            ]
            if i == 0:
                cmd.extend(["--session-id", sid])
            else:
                cmd.extend(["--continue"])
            cmds.append(cmd)
        return cmds
