"""Kimi Code CLI plugin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..common import HOME, KEY_ENV, PROVIDER_ID, append_text
from ._base import AgentPlugin

DEFAULT_CONTEXT_SIZE = 256000


def _section_has_context(section: str) -> bool:
    for line in section.splitlines():
        if line.strip().startswith("max_context_size"):
            return True
    return False


def ensure_model_context(
    text: str,
    mid: str,
    size: int = DEFAULT_CONTEXT_SIZE,
) -> tuple[str, bool]:
    """Insert max_context_size into an existing [models] block."""
    header = f'[models."{PROVIDER_ID}/{mid}"]'
    start = text.find(header)
    if start < 0:
        return text, False
    after = start + len(header)
    nxt = text.find("\n[", after)
    section = text[start:] if nxt < 0 else text[start:nxt]
    if _section_has_context(section):
        return text, False
    insert = f"\nmax_context_size = {size}"
    return text[:after] + insert + text[after:], True


class KimiAgent(AgentPlugin):
    name = "kimi"
    binary = "kimi"
    supports_custom_openai = True
    notes = "kimi -p -m provider/model"

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        path = HOME / ".kimi-code" / "config.toml"
        text = path.read_text() if path.is_file() else ""
        changed = False
        header = f"[providers.{PROVIDER_ID}]"
        if header not in text:
            key = os.environ.get(KEY_ENV, "")
            append_text(
                path,
                f"\n{header}\n"
                'type = "openai"\n'
                + (f'api_key = "{key}"\n' if key else "")
                + f'base_url = "{base_url}"\n',
            )
            text = path.read_text() if path.is_file() else ""
            changed = True
        added: list[str] = []
        patched: list[str] = []
        chunks: list[str] = []
        for mid in models:
            block = f'[models."{PROVIDER_ID}/{mid}"]'
            if block in text:
                text, did = ensure_model_context(text, mid)
                if did:
                    patched.append(mid)
                    changed = True
                continue
            chunks.append(
                f"\n{block}\n"
                f'provider = "{PROVIDER_ID}"\n'
                f'model = "{mid}"\n'
                f"max_context_size = {DEFAULT_CONTEXT_SIZE}\n"
                "capabilities = [ \"tool_use\" ]\n"
            )
            added.append(mid)
        if patched:
            path.write_text(text)
        if chunks:
            append_text(path, "".join(chunks))
            changed = True
        return {
            "ok": True,
            "path": str(path),
            "changed": changed,
            "added": added,
            "patched": patched,
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
        full = f"{PROVIDER_ID}/{model}"
        cmds: list[list[str]] = []
        for i, prompt in enumerate(prompts):
            cmd = ["kimi", "-p", prompt, "-m", full]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
