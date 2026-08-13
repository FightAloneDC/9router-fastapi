"""Agent plugin registry — one import per agent module."""

from __future__ import annotations

from ._base import AgentPlugin, StubAgent
from .aider import AiderAgent
from .claude import ClaudeAgent
from .cline import ClineAgent
from .codex import CodexAgent
from .commandcode import make_commandcode
from .copilot import CopilotAgent
from .crush import CrushAgent
from .grok import GrokAgent
from .hermes import HermesAgent
from .kilo import KiloAgent
from .kimi import KimiAgent
from .mimo import MimoAgent
from .opencode import OpenCodeAgent
from .pi import PiAgent
from .qwen import QwenAgent
from .reasonix import ReasonixAgent
from .vibe import VibeAgent

_IMPLEMENTED: list[AgentPlugin] = [
    HermesAgent(),
    PiAgent(),
    AiderAgent(),
    CodexAgent(),
    OpenCodeAgent(),
    QwenAgent(),
    CrushAgent(),
    KiloAgent(),
    ClaudeAgent(),
    GrokAgent(),
    VibeAgent(),
    KimiAgent(),
    ClineAgent(),
    make_commandcode("cmd", "cmd"),
    CopilotAgent(),
    MimoAgent(),
    ReasonixAgent(),
]

_OTHER: list[AgentPlugin] = [
    StubAgent("cmdc", "cmdc", skip_reason="alias of cmd"),
    StubAgent(
        "command-code",
        "command-code",
        skip_reason="alias of cmd",
    ),
    StubAgent(
        "commandcode",
        "commandcode",
        skip_reason="alias of cmd",
    ),
    StubAgent("kilocode", "kilocode", skip_reason="alias of kilo"),
    StubAgent("agent", "agent", skip_reason="alias of cursor-agent"),
    StubAgent("cursor", "cursor", skip_reason="alias of cursor-agent"),
    StubAgent(
        "agy",
        "agy",
        skip_reason="Gemini catalog only",
    ),
    StubAgent(
        "kimchi",
        "kimchi",
        skip_reason="kimchi-dev catalog only",
    ),
    StubAgent(
        "droid",
        "droid",
        skip_reason="Factory auth missing",
    ),
    StubAgent(
        "cursor-agent",
        "cursor-agent",
        skip_reason="no custom provider",
    ),
    StubAgent(
        "qodercli",
        "qodercli",
        skip_reason="no custom provider",
    ),
    StubAgent(
        "zero",
        "zero",
        skip_reason="own encrypted provider config",
    ),
    StubAgent(
        "kiro-cli",
        "kiro-cli",
        skip_reason="Kiro OAuth only",
    ),
    StubAgent(
        "kiro-cli-chat",
        "kiro-cli-chat",
        skip_reason="alias of kiro-cli",
    ),
    StubAgent(
        "kiro-cli-term",
        "kiro-cli-term",
        notes="terminal helper",
        skip_reason="not a chat CLI",
    ),
    StubAgent(
        "vibe-acp",
        "vibe-acp",
        notes="ACP server",
        skip_reason="ACP server, not a chat CLI",
    ),
    StubAgent(
        "vibe-app-server",
        "vibe-app-server",
        notes="app server",
        skip_reason="HTTP server, not a chat CLI",
    ),
]


def all_plugins() -> list[AgentPlugin]:
    return [*_IMPLEMENTED, *_OTHER]


def list_agents() -> list[AgentPlugin]:
    return all_plugins()


def get_agent(name: str) -> AgentPlugin | None:
    for plugin in all_plugins():
        if plugin.name == name:
            return plugin
    return None


def runnable_agents(names: set[str] | None = None) -> list[AgentPlugin]:
    out: list[AgentPlugin] = []
    for plugin in _IMPLEMENTED:
        if names and plugin.name not in names:
            continue
        if not plugin.supports_custom_openai:
            continue
        if plugin.skip_reason:
            continue
        if not plugin.available():
            continue
        out.append(plugin)
    return out
