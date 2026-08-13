"""Kimchi harness — swap llmEndpoint to 9Router, then restore."""

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
)
from ._base import AgentPlugin

_BAK = "config.json.9router-farm.bak"
_NONE = "config.json.9router-farm.none"


class KimchiAgent(AgentPlugin):
    name = "kimchi"
    binary = "kimchi"
    supports_custom_openai = True
    notes = "backup config.json llmEndpoint -> 9Router"

    def _home(self) -> Path:
        return getattr(self, "home", HOME)

    def _cfg_dir(self) -> Path:
        return self._home() / ".config" / "kimchi"

    def _settings(self) -> Path:
        return self._cfg_dir() / "config.json"

    def _backup(self) -> Path:
        return self._cfg_dir() / _BAK

    def _none(self) -> Path:
        return self._cfg_dir() / _NONE

    def extra_env(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
    ) -> dict[str, str]:
        del model, base_url
        return {"KIMCHI_API_KEY": api_key}

    def prepare(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        del models
        self._cfg_dir().mkdir(parents=True, exist_ok=True)
        settings = self._settings()
        backup = self._backup()
        none = self._none()
        if backup.is_file() or none.is_file():
            self.teardown()
        if settings.is_file():
            shutil.copy2(settings, backup)
            data = load_json_config(backup)
            had = True
        else:
            none.write_text("")
            data = {}
            had = False
        key = os.environ.get(KEY_ENV, "")
        data["llmEndpoint"] = base_url
        if key:
            data["apiKey"] = key
        data.pop("providers", None)
        atomic_write_json(settings, data)
        settings.chmod(0o600)
        return {
            "ok": True,
            "changed": True,
            "path": str(settings),
            "backup": str(backup) if had else "",
            "llmEndpoint": base_url,
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
                "note": "removed farm-only config",
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
                "kimchi",
                "-p",
                prompt,
                "--provider",
                "kimchi-dev",
                "--model",
                model,
                "--yolo",
            ]
            if i > 0:
                cmd.append("--continue")
            cmds.append(cmd)
        return cmds
