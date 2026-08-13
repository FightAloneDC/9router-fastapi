"""Claude Code via 9Router /v1/messages.

Swaps ~/.claude/settings.json for the farm run, then restores it.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from ..common import (
    HOME,
    KEY_ENV,
    atomic_write_json,
    load_json_config,
    strip_v1,
)
from ._base import AgentPlugin

_BAK = "settings.json.9router-farm.bak"
_NONE = "settings.json.9router-farm.none"


class ClaudeAgent(AgentPlugin):
    name = "claude"
    binary = "claude"
    supports_custom_openai = True
    notes = "backup settings.json; ANTHROPIC_* -> 9Router"

    def _home(self) -> Path:
        return getattr(self, "home", HOME)

    def _claude_dir(self) -> Path:
        return self._home() / ".claude"

    def _settings(self) -> Path:
        return self._claude_dir() / "settings.json"

    def _backup(self) -> Path:
        return self._claude_dir() / _BAK

    def _none(self) -> Path:
        return self._claude_dir() / _NONE

    def extra_env(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
    ) -> dict[str, str]:
        env = {
            "ANTHROPIC_API_KEY": api_key,
            "ANTHROPIC_AUTH_TOKEN": api_key,
            "ANTHROPIC_BASE_URL": strip_v1(base_url),
        }
        if model:
            env["ANTHROPIC_MODEL"] = model
        return env

    def prepare(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        claude_dir = self._claude_dir()
        claude_dir.mkdir(parents=True, exist_ok=True)
        settings = self._settings()
        backup = self._backup()
        none = self._none()
        if backup.is_file() or none.is_file():
            self.teardown()
        if settings.is_file():
            shutil.copy2(settings, backup)
            had = True
        else:
            none.write_text("")
            had = False
        key = os.environ.get(KEY_ENV, "")
        farm: dict[str, Any] = {
            "env": {
                "ANTHROPIC_AUTH_TOKEN": key,
                "ANTHROPIC_API_KEY": key,
                "ANTHROPIC_BASE_URL": strip_v1(base_url),
            }
        }
        if models:
            farm["env"]["ANTHROPIC_MODEL"] = models[0]
        if had:
            old = load_json_config(backup)
            perms = old.get("permissions")
            if isinstance(perms, dict):
                farm["permissions"] = perms
        atomic_write_json(settings, farm)
        return {
            "ok": True,
            "changed": True,
            "path": str(settings),
            "backup": str(backup) if had else "",
            "anthropic_base": strip_v1(base_url),
        }

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        return self.prepare(base_url, models)

    def teardown(self) -> dict[str, Any]:
        settings = self._settings()
        backup = self._backup()
        none = self._none()
        if backup.is_file():
            shutil.copy2(backup, settings)
            backup.unlink()
            if none.is_file():
                none.unlink()
            return {
                "ok": True,
                "restored": True,
                "path": str(settings),
            }
        if none.is_file():
            if settings.is_file():
                settings.unlink()
            none.unlink()
            return {
                "ok": True,
                "restored": True,
                "path": str(settings),
                "note": "removed farm-only settings",
            }
        return {"ok": True, "skipped": True}

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
                "claude",
                "-p",
                prompt,
                "--bare",
                "--output-format",
                "text",
                "--model",
                model,
                "--dangerously-skip-permissions",
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
