"""Best-effort file dump of grok-cli client I/O for debugging.

Writes paired JSON files under ``.scratch/grok-cli/`` (gitignored):

* ``{stamp}_{rid}_client.json`` — client body + upstream body
* ``{stamp}_{rid}_response.json`` — assembled content / tools / usage

Off unless ``GROK_CLI_DUMP=true`` in ``.env`` (or ``GROK_CLI_DUMP=1``
in the process environment). Override the directory with
``GROK_CLI_DUMP_DIR``. Never raises into the proxy path.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SECRET_KEYS = frozenset({
    "apikey",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "authorization",
    "cookie",
    "setcookie",
})


def dump_enabled() -> bool:
    """True only when GROK_CLI_DUMP is explicitly on.

    Process env wins. Otherwise the backend ``.env`` file is read on
    every call (commented lines are ignored) so toggling the key does
    not require restarting uvicorn. Cached Settings is not used —
    pydantic loads .env once at import and ``--reload`` does not
    watch ``.env``.
    """
    flag = os.environ.get("GROK_CLI_DUMP", "").strip().lower()
    if flag:
        return flag in ("1", "true", "on", "yes")
    file_flag = _dotenv_value("GROK_CLI_DUMP")
    if file_flag is None:
        return False
    return file_flag.strip().lower() in ("1", "true", "on", "yes")


def _dotenv_value(name: str) -> str | None:
    here = Path(__file__).resolve()
    candidates = (
        here.parents[3] / ".env",
        Path.cwd() / ".env",
    )
    seen: set[Path] = set()
    for path in candidates:
        try:
            path = path.resolve()
        except OSError:
            continue
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if not line.startswith(name + "="):
                continue
            return line.split("=", 1)[1].strip().strip("'\"")
    return None


def resolve_dump_dir() -> Path:
    configured = os.environ.get("GROK_CLI_DUMP_DIR", "").strip()
    if not configured:
        try:
            from app.config import settings
            configured = (settings.GROK_CLI_DUMP_DIR or "").strip()
        except Exception:
            configured = ""
    if configured:
        path = Path(configured)
    else:
        data = os.environ.get("DATA_DIR")
        if data:
            path = Path(data) / "grok-cli"
        else:
            repo = Path(__file__).resolve().parents[4]
            path = repo / ".scratch" / "grok-cli"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_upstream_body(
    raw_body: bytes | None,
    fallback: dict | None,
) -> dict | None:
    if raw_body:
        try:
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            return {
                "_unparsed": True,
                "_bytes": len(raw_body),
            }
    return fallback


@dataclass
class DumpSession:
    request_id: str
    directory: Path
    client_path: Path
    response_path: Path
    endpoint: str
    stream: bool


def begin_dump(
    *,
    request_id: str,
    endpoint: str,
    stream: bool,
    client_request: dict | None,
    upstream_request: dict | None,
    model: str = "",
    connection_id: str | None = None,
    provider: str = "grok-cli",
) -> DumpSession | None:
    if not dump_enabled():
        return None
    try:
        directory = resolve_dump_dir()
        stamp = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ",
        )
        rid = (request_id or "unknown").replace("/", "_")[:12]
        prefix = f"{stamp}_{rid}"
        session = DumpSession(
            request_id=request_id,
            directory=directory,
            client_path=directory / f"{prefix}_client.json",
            response_path=directory / f"{prefix}_response.json",
            endpoint=endpoint,
            stream=stream,
        )
        payload = {
            "meta": {
                "request_id": request_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint,
                "stream": stream,
                "provider": provider,
                "model": model,
                "connection_id": connection_id,
            },
            "client_request": _redact_secrets(client_request),
            "upstream_request": _redact_secrets(upstream_request),
        }
        _atomic_write(session.client_path, payload)
        print(
            f"[grok-cli dump] client {session.client_path}",
            flush=True,
        )
        return session
    except Exception as exc:
        print(f"[grok-cli dump] begin failed: {exc}", flush=True)
        return None


def finish_dump(
    session: DumpSession | None,
    response: dict | None,
    status: str = "ok",
    error: str | None = None,
) -> None:
    if session is None or not dump_enabled():
        return
    try:
        assembled = dict(response or {})
        tool_calls = assembled.get("tool_calls") or []
        names = [
            ((tc.get("function") or {}).get("name") or "")
            for tc in tool_calls
            if isinstance(tc, dict)
        ]
        content = assembled.get("content") or ""
        reasoning = assembled.get("reasoning_content") or ""
        payload = {
            "meta": {
                "request_id": session.request_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "endpoint": session.endpoint,
                "stream": session.stream,
                "status": status,
                "content_chars": len(content),
                "reasoning_chars": len(reasoning),
                "tool_call_names": [n for n in names if n],
                "finish_reason": assembled.get("finish_reason"),
                "usage": assembled.get("usage") or {},
                "chunk_count": assembled.get("chunk_count"),
            },
            "response": assembled,
            "error": error,
        }
        _atomic_write(session.response_path, payload)
        print(
            f"[grok-cli dump] response {session.response_path}",
            flush=True,
        )
    except Exception as exc:
        print(f"[grok-cli dump] finish failed: {exc}", flush=True)


def response_from_chat_completion(obj: dict | None) -> dict:
    """Normalize a Chat Completions JSON object for the dump file."""
    if not isinstance(obj, dict):
        return {
            "content": "",
            "reasoning_content": "",
            "tool_calls": [],
            "finish_reason": None,
            "usage": {},
        }
    choice = (obj.get("choices") or [{}])[0] or {}
    msg = choice.get("message") or {}
    return {
        "content": msg.get("content") or "",
        "reasoning_content": msg.get("reasoning_content") or "",
        "tool_calls": msg.get("tool_calls") or [],
        "finish_reason": choice.get("finish_reason"),
        "usage": obj.get("usage") or {},
        "id": obj.get("id"),
        "model": obj.get("model"),
    }


class ChatSseAssembler:
    """Rebuild one Chat Completions message from outbound SSE chunks."""

    def __init__(self) -> None:
        self.content_parts: list[str] = []
        self.reasoning_parts: list[str] = []
        self.tool_calls: dict[int, dict] = {}
        self.finish_reason: str | None = None
        self.usage: dict = {}
        self.errors: list[Any] = []
        self.chunk_count = 0

    def feed(self, sse: str) -> None:
        if not sse:
            return
        for payload in _iter_data_payloads(sse):
            if payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(obj, dict):
                continue
            self.chunk_count += 1
            if obj.get("error"):
                self.errors.append(obj["error"])
            if obj.get("usage"):
                self.usage = obj["usage"]
            choices = obj.get("choices") or []
            if not choices:
                continue
            choice = choices[0] or {}
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str) and content:
                self.content_parts.append(content)
            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                self.reasoning_parts.append(reasoning)
            for tc in delta.get("tool_calls") or []:
                if isinstance(tc, dict):
                    self._merge_tool_call(tc)

    def to_dict(self) -> dict:
        tools = [
            self.tool_calls[idx]
            for idx in sorted(self.tool_calls)
        ]
        return {
            "content": "".join(self.content_parts),
            "reasoning_content": "".join(self.reasoning_parts),
            "tool_calls": tools,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "chunk_count": self.chunk_count,
            "errors": self.errors,
        }

    def _merge_tool_call(self, tc: dict) -> None:
        idx = tc.get("index", 0)
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            idx = 0
        slot = self.tool_calls.setdefault(idx, {
            "id": "",
            "type": "function",
            "function": {"name": "", "arguments": ""},
        })
        if tc.get("id"):
            slot["id"] = tc["id"]
        if tc.get("type"):
            slot["type"] = tc["type"]
        fn = tc.get("function") or {}
        if fn.get("name"):
            slot["function"]["name"] = fn["name"]
        if fn.get("arguments"):
            slot["function"]["arguments"] += fn["arguments"]


def _iter_data_payloads(sse: str) -> list[str]:
    payloads: list[str] = []
    for raw_line in sse.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payloads.append(line[5:].strip())
    return payloads


def _normalize_key(key: str) -> str:
    return key.lower().replace("-", "").replace("_", "")


def _redact_secrets(obj: Any) -> Any:
    """Redact token-like keys. Does not recurse into messages."""
    if not isinstance(obj, dict):
        return obj
    out: dict[str, Any] = {}
    for key, value in obj.items():
        if _normalize_key(str(key)) in _SECRET_KEYS:
            out[key] = "[redacted]"
        elif (
            str(key).lower() == "headers"
            and isinstance(value, dict)
        ):
            out[key] = _redact_secrets(value)
        else:
            out[key] = value
    return out


def _atomic_write(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
