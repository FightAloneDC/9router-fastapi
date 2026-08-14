"""Tool host lists and /etc/hosts DNS helpers.

Hosts match decolua/9router src/shared/constants/mitmToolHosts.js.
"""

from __future__ import annotations

from pathlib import Path

HOSTS_FILE = Path("/etc/hosts")
MARKER = "# 9router-mitm"

TOOL_HOSTS: dict[str, list[str]] = {
    "antigravity": [
        "daily-cloudcode-pa.googleapis.com",
        "cloudcode-pa.googleapis.com",
    ],
    "copilot": [
        "api.individual.githubcopilot.com",
    ],
    "kiro": [
        "runtime.us-east-1.kiro.dev",
        "q.us-east-1.amazonaws.com",
        "codewhisperer.us-east-1.amazonaws.com",
    ],
    "cursor": [
        "api2.cursor.sh",
    ],
}

TARGET_HOSTS: frozenset[str] = frozenset(
    host for hosts in TOOL_HOSTS.values() for host in hosts
)

URL_PATTERNS: dict[str, list[str]] = {
    "antigravity": [":generateContent", ":streamGenerateContent"],
    "copilot": ["/chat/completions", "/v1/messages", "/responses"],
    "kiro": ["/generateAssistantResponse"],
    "cursor": ["/BidiAppend", "/RunSSE", "/RunPoll", "/Run"],
}


def get_tool_for_host(host: str | None) -> str | None:
    name = (host or "").split(":")[0].lower()
    for tool, hosts in TOOL_HOSTS.items():
        if name in hosts:
            return tool
    return None


def check_all_dns_status() -> dict[str, bool]:
    try:
        text = HOSTS_FILE.read_text(encoding="utf-8")
    except OSError:
        return {tool: False for tool in TOOL_HOSTS}
    return {
        tool: all(host in text for host in hosts)
        for tool, hosts in TOOL_HOSTS.items()
    }


def _desired_lines(tool: str) -> list[str]:
    return [f"127.0.0.1 {h} {MARKER}" for h in TOOL_HOSTS.get(tool, [])]


def apply_dns(tool: str, enabled: bool) -> None:
    """Best-effort /etc/hosts update. Raises OSError if not writable."""
    if tool not in TOOL_HOSTS:
        raise ValueError(f"Unknown MITM tool: {tool}")
    text = HOSTS_FILE.read_text(encoding="utf-8")
    lines = text.splitlines()
    drop = set(TOOL_HOSTS[tool])
    kept = [
        line for line in lines
        if not any(host in line and MARKER in line for host in drop)
        and not any(
            line.strip().startswith("127.0.0.1") and host in line
            for host in drop
        )
    ]
    if enabled:
        kept.extend(_desired_lines(tool))
    body = "\n".join(kept).rstrip() + "\n"
    HOSTS_FILE.write_text(body, encoding="utf-8")
