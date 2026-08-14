"""Detect grok-cli phantom-write replies and retry with an inject.

The model can Write (simple ``grok-test.txt`` succeeded). Long
file-write tasks often finish ``stop`` with no tool. On that
pattern, retry once with an injected user turn — do not mark the
connection and do not invent a Write payload.

Formula (all must hold) before retry:

1. Client advertised Write or Edit
2. Some user message has file-write intent
3. ``finish_reason == stop``
4. This reply called no mutating file tools
5. Assistant content is non-empty
6. History has no prior Write/Edit/Bash in this request
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

WRITE_TOOL_NAMES = frozenset({"write", "edit"})
# This reply: Write/Edit/StrReplace count as "did persist a file".
# Bash is not included — `go test` / `ls` must not suppress retry.
FILE_WRITE_TOOL_NAMES = frozenset({
    "write", "edit", "strreplace",
})
MUTATING_TOOL_NAMES = FILE_WRITE_TOOL_NAMES

# User asked to persist something to a file / document.
# Keep this wider than "simpan ke file" — real prompts insert words
# ("simpan hasilnya ke file") or say "tulis file X" / "tool Write".
# Path-like: docs/foo.md or `foo.txt` — users often omit the word "file".
_PATH_LIKE = r"(?:file|dokumen|path|`?[\w./\\-]+\.[A-Za-z0-9]{1,8}`?)"

_WRITE_INTENT_RE = re.compile(
    r"("
    r"tulis(?:kan)?\s+(?:ke\s+)?" + _PATH_LIKE + r"|"
    r"ke\s+file\s+dokumen|"
    r"simpan(?:\s+\w+){0,4}\s+ke\s+" + _PATH_LIKE + r"|"
    r"buat(?:kan)?\s+(?:sebuah\s+)?file|"
    r"tool\s+write|"
    r"write\s+(?:it\s+|this\s+|the\s+)?"
    r"(?:to\s+)?(?:a\s+)?" + _PATH_LIKE + r"|"
    r"save\s+(?:it\s+|this\s+|the\s+)?(?:to|into)\s+"
    + _PATH_LIKE + r"|"
    r"create\s+(?:a\s+)?(?:file|document)\s+"
    r")",
    re.IGNORECASE,
)

RETRY_USER_TEXT = (
    "You just claimed a file was written but you did not call "
    "the Write or Edit tool. Call Write now with the full file "
    "contents and the exact path the user requested. Do not only "
    "describe the file in chat."
)


def tool_names(request: dict | None) -> set[str]:
    names: set[str] = set()
    if not isinstance(request, dict):
        return names
    for item in request.get("tools") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or ""
        fn = item.get("function")
        if isinstance(fn, dict):
            name = fn.get("name") or name
        if name:
            names.add(str(name).lower())
    return names


def request_has_write_tools(request: dict | None) -> bool:
    return bool(tool_names(request) & WRITE_TOOL_NAMES)


def called_tool_names(assembled: dict | None) -> set[str]:
    names: set[str] = set()
    if not isinstance(assembled, dict):
        return names
    for item in assembled.get("tool_calls") or []:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") or {}
        name = item.get("name") or fn.get("name") or ""
        if name:
            names.add(str(name).lower())
    return names


def iter_user_texts(request: dict | None):
    if not isinstance(request, dict):
        return
    for message in request.get("messages") or []:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "user":
            continue
        yield from _content_texts(message.get("content"))
    for item in request.get("input") or []:
        if not isinstance(item, dict):
            continue
        if item.get("role") != "user":
            continue
        yield from _content_texts(item.get("content"))


def user_has_write_intent(request: dict | None) -> bool:
    for text in iter_user_texts(request):
        if _WRITE_INTENT_RE.search(text):
            return True
    return False


def history_has_mutating_write(request: dict | None) -> bool:
    """True if an earlier assistant turn already called Write/Edit."""
    if not isinstance(request, dict):
        return False
    for message in request.get("messages") or []:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "assistant":
            continue
        for item in message.get("tool_calls") or []:
            if not isinstance(item, dict):
                continue
            fn = item.get("function") or {}
            name = item.get("name") or fn.get("name") or ""
            if str(name).lower() in FILE_WRITE_TOOL_NAMES:
                return True
    return False


def evaluate_phantom_write(
    client_request: dict | None,
    assembled: dict | None,
) -> dict[str, bool]:
    """Return each formula signal plus the combined hit."""
    content = ""
    finish = ""
    if isinstance(assembled, dict):
        raw = assembled.get("content") or ""
        content = raw if isinstance(raw, str) else ""
        finish = assembled.get("finish_reason") or ""
    signals = {
        "write_tools": request_has_write_tools(client_request),
        "user_intent": user_has_write_intent(client_request),
        "stop": finish == "stop",
        "no_mutate": not bool(
            called_tool_names(assembled) & MUTATING_TOOL_NAMES,
        ),
        "has_content": bool(content.strip()),
        "fresh": not history_has_mutating_write(client_request),
    }
    signals["hit"] = all((
        signals["write_tools"],
        signals["user_intent"],
        signals["stop"],
        signals["no_mutate"],
        signals["has_content"],
        signals["fresh"],
    ))
    return signals


def is_phantom_write(
    client_request: dict | None,
    assembled: dict | None,
) -> bool:
    """True when the model closed a file-write task without writing."""
    return evaluate_phantom_write(client_request, assembled)["hit"]


def inject_retry_upstream(
    upstream: dict,
    assembled: dict | None,
) -> dict:
    """Copy the Responses body and append a user nudge.

    Assistant items use ``input_text`` like ``chat_to_responses_request``.
    ``output_text`` was rejected by upstream (retry returned no dump).
    ``tool_choice=required`` forces a tool on this retry only.
    """
    out = dict(upstream)
    items = list(out.get("input") or [])
    content = ""
    if isinstance(assembled, dict):
        raw = assembled.get("content") or ""
        if isinstance(raw, str):
            content = raw.strip()
    nudge = RETRY_USER_TEXT
    if content:
        clip = content[:500]
        nudge = (
            f"Your previous reply (no tool call) was:\n{clip}\n\n"
            f"{RETRY_USER_TEXT}"
        )
    items.append({
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": nudge}],
    })
    out["input"] = items
    out["stream"] = True
    out["tool_choice"] = "required"
    return out


async def maybe_mark_phantom_write(
    db: Any,
    connection_id: str | None,
    client_request: dict | None,
    assembled: dict | None,
    request_id: str = "",
) -> bool:
    """Mark the connection anomalous if this reply is a phantom write.

    Never raises into the proxy path. Returns True when a new mark
    was written.
    """
    if db is None or not connection_id:
        return False
    try:
        signals = evaluate_phantom_write(client_request, assembled)
        if not signals["hit"]:
            return False
        from app.services.proxy import mark_connection_anomaly

        reason = (
            "Phantom write: user asked to write a file, "
            "finish=stop, no Write/Edit/Bash"
        )
        marked = await mark_connection_anomaly(
            db,
            connection_id,
            reason=reason,
            request_id=request_id,
        )
        if marked:
            logger.warning(
                "grok-cli anomaly marked conn=%s req=%s signals=%s",
                connection_id,
                request_id,
                signals,
            )
        return marked
    except Exception as exc:
        logger.warning("grok-cli anomaly mark failed: %s", exc)
        return False


def _content_texts(content: Any):
    if isinstance(content, str):
        yield content
        return
    if not isinstance(content, list):
        return
    for part in content:
        if isinstance(part, str):
            yield part
        elif isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str):
                yield text
