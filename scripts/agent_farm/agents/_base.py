"""Base plugin interface for one agent CLI."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..common import which


class AgentPlugin(ABC):
    """One module = one agent. Implement ensure + build_cmds only."""

    name: str = ""
    binary: str = ""
    # True only when OpenAI-compat custom base URL is supported.
    supports_custom_openai: bool = False
    notes: str = ""
    # If set, agent is listed but never selected for farm runs.
    skip_reason: str = ""
    # Cline and similar CLIs refuse pipes; runner allocates a PTY.
    needs_pty: bool = False

    def available(self) -> bool:
        return which(self.binary) is not None

    def binary_path(self) -> str | None:
        return which(self.binary)

    def extra_env(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
    ) -> dict[str, str]:
        """Optional extra env for this session. Default: none."""
        del api_key, base_url, model
        return {}

    def prepare(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        """Optional swap of user config before jobs. Default: none."""
        del base_url, models
        return {"ok": True, "skipped": True}

    def teardown(self) -> dict[str, Any]:
        """Restore user config after jobs. Default: none."""
        return {"ok": True, "skipped": True}

    @abstractmethod
    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        """Merge custom provider into agent config. Never wipe others."""

    @abstractmethod
    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        """Return one argv list per prompt turn (same session)."""


class StubAgent(AgentPlugin):
    """Placeholder until custom-provider wiring is confirmed."""

    supports_custom_openai = False

    def __init__(
        self,
        name: str,
        binary: str,
        notes: str = "",
        skip_reason: str = "not wired yet",
    ) -> None:
        self.name = name
        self.binary = binary
        self.notes = notes
        self.skip_reason = skip_reason

    def ensure(
        self,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        del base_url, models
        return {
            "ok": False,
            "skipped": True,
            "reason": self.skip_reason,
        }

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        del model, prompts, work_dir, api_key, session_id
        raise NotImplementedError(
            f"{self.name}: custom OpenAI provider not wired"
        )
