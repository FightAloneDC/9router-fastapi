"""Codex agent plugin."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..common import (
    HERMES_ENV_FILE,
    HOME,
    KEY_ENV,
    PROVIDER_NAME,
    atomic_write_text,
)
from ._base import AgentPlugin

CODEX_PROVIDER = "fastapi_9router_8013"
CODEX_MARKER = f"[model_providers.{CODEX_PROVIDER}]"


def patch_codex_wire_api(text: str) -> tuple[str, bool]:
    """Force wire_api=responses on the farm provider (chat is rejected)."""
    idx = text.find(CODEX_MARKER)
    if idx < 0:
        return text, False
    rest = text[idx + len(CODEX_MARKER):]
    nxt = re.search(r"\n\[", rest)
    end = idx + len(CODEX_MARKER) + (
        nxt.start() if nxt else len(rest)
    )
    section = text[idx:end]
    if 'wire_api = "responses"' in section:
        return text, False
    new_section, n = re.subn(
        r'wire_api\s*=\s*"[^"]*"',
        'wire_api = "responses"',
        section,
        count=1,
    )
    if n == 0:
        new_section = (
            section.rstrip() + '\nwire_api = "responses"\n'
        )
    return text[:idx] + new_section + text[end:], True


class CodexAgent(AgentPlugin):
    name = "codex"
    binary = "codex"
    supports_custom_openai = True
    notes = "codex exec + resume --last in per-job cwd"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".codex" / "config.toml"
        if not path.is_file():
            return {"ok": False, "error": f"missing {path}"}
        text = path.read_text()
        changed = False
        if CODEX_MARKER not in text:
            block = (
                f"\n{CODEX_MARKER}\n"
                f'name = "{PROVIDER_NAME} 8013"\n'
                f'base_url = "{base_url}"\n'
                f'env_key = "{KEY_ENV}"\n'
                f'wire_api = "responses"\n'
            )
            text = text.rstrip() + "\n" + block
            changed = True
        text, patched = patch_codex_wire_api(text)
        if patched:
            changed = True
        if changed:
            if not text.endswith("\n"):
                text += "\n"
            atomic_write_text(path, text)
        env_path = HOME / ".codex" / ".env"
        env_lines: list[str] = []
        if env_path.is_file():
            env_lines = env_path.read_text().splitlines()
        if not any(line.startswith(f"{KEY_ENV}=") for line in env_lines):
            key = os.environ.get(KEY_ENV, "")
            if not key and HERMES_ENV_FILE.is_file():
                for line in HERMES_ENV_FILE.read_text().splitlines():
                    if line.startswith(f"{KEY_ENV}="):
                        key = line.split("=", 1)[1].strip()
                        break
            if key:
                env_lines.append(f"{KEY_ENV}={key}")
                atomic_write_text(
                    env_path,
                    "\n".join(env_lines) + "\n",
                )
                changed = True
        return {
            "ok": True,
            "path": str(path),
            "changed": changed,
            "models_noted": len(models),
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
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            if i == 0:
                cmds.append(
                    [
                        "codex",
                        "exec",
                        "-m",
                        model,
                        "-c",
                        'model_provider="fastapi_9router_8013"',
                        "--skip-git-repo-check",
                        "-C",
                        str(work_dir),
                        prompt,
                    ]
                )
            else:
                cmds.append(
                    [
                        "codex",
                        "exec",
                        "resume",
                        "--last",
                        "-C",
                        str(work_dir),
                        prompt,
                    ]
                )
        return cmds
