"""Sanitize Morph chat bodies and unwrap Apply responses.

Apply contract (docs Apply API / OpenAPI ChatCompletionRequest):
https://docs.morphllm.com/api-reference/endpoint/apply.md

Input (always one user message):

  <instruction>...</instruction>
  <code>...</code>
  <update>...</update>

Output: docs examples put the merged file in
``choices[0].message.content`` (often plain text). When Morph
returns XML-tagged content (``<code>``, ``<reply>``, full Apply
envelope), the proxy unwraps it for the client.

Allowed fields: model, messages, stream, max_tokens, temperature.
Warp Grep and Fast Models keep their own shapes.
"""

from __future__ import annotations

import json
import re

_APPLY_MODELS = frozenset({
    "morph-v3-fast",
    "morph-v3-large",
    "auto",
})

_APPLY_KEYS = frozenset({
    "model",
    "messages",
    "stream",
    "max_tokens",
    "temperature",
})

_DROP_ALWAYS = (
    "store",
)

# Live 2026-08-18: chat wrap must NOT put user text in <update>
# (echo) and must NOT use the docs unchanged-code marker alone with
# empty <code> (Morph returns the marker). Working chat update body
# for morph-v3-large / auto:
_APPLY_CHAT_UPDATE = "(no file edit; reply as chat)"

# morph-v3-fast live 2026-08-18: empty code/update → blank; the
# large chat marker is echoed; one space in both slots + last user
# in <instruction> returns a reply without dumping system text.
_APPLY_FAST_SLOT = " "

_REPLY_TAG_RE = re.compile(
    r"<reply>(.*?)</reply>",
    re.IGNORECASE | re.DOTALL,
)
_CODE_TAG_RE = re.compile(
    r"<code>(.*?)</code>",
    re.IGNORECASE | re.DOTALL,
)
_THINK_TAG_RE = re.compile(
    r"<think>(.*?)</think>",
    re.IGNORECASE | re.DOTALL,
)
_TOOL_CALL_TAG_RE = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>",
    re.IGNORECASE | re.DOTALL,
)


def model_tail(model: object) -> str:
    raw = str(model or "").strip()
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    return raw


def is_apply_model(model: object) -> bool:
    return model_tail(model) in _APPLY_MODELS


def is_warp_grep_model(model: object) -> bool:
    return model_tail(model).startswith("morph-warp-grep")


def flatten_content(content: object) -> str | None:
    """Turn OpenAI content (str / list / dict) into a string."""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
        return str(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        return "".join(parts)
    return str(content)


def joined_message_text(messages: list) -> str:
    parts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        text = msg.get("content")
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n".join(parts)


def looks_like_apply_payload(messages: list) -> bool:
    """Official Apply XML: <code>…</code> and <update>…</update>."""
    blob = joined_message_text(messages).lower()
    return "<code>" in blob and "<update>" in blob


def last_user_text(messages: list) -> str:
    last = ""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if str(msg.get("role") or "").strip().lower() != "user":
            continue
        text = msg.get("content")
        if isinstance(text, str) and text.strip():
            last = text.strip()
    return last


def looks_like_apply_last_user(messages: list) -> bool:
    """Apply XML on the last user turn only (ignore Pi system)."""
    blob = last_user_text(messages).lower()
    return "<code>" in blob and "<update>" in blob


def normalize_message(message: object) -> dict | object:
    if not isinstance(message, dict):
        return message
    out = dict(message)
    if "content" not in out:
        return out
    content = out.get("content")
    if content is None:
        # Kimi K3: omit content when tools are present.
        if out.get("tools") or out.get("tool_calls"):
            out.pop("content", None)
            return out
        return out
    out["content"] = flatten_content(content)
    if out.get("role") == "developer":
        out["role"] = "system"
    return out


def strip_client_tools(body: dict) -> dict:
    out = dict(body)
    out.pop("tools", None)
    out.pop("tool_choice", None)
    out.pop("parallel_tool_calls", None)
    return out


def client_has_tools(body: dict) -> bool:
    tools = body.get("tools")
    return isinstance(tools, list) and bool(tools)


def sanitize_morph_tools(body: dict) -> dict:
    """Fast Models: keep tools (catalog tools:true).

    Live 2026-08-18: morph-qwen* / morph-kimik3 accept tools with
    omitted or auto tool_choice and return OpenAI tool_calls. Do NOT
    strip tools here — that broke Pi agent on Fast Models.
    """
    return body


def prepare_apply_tools_body(body: dict) -> dict:
    """Apply + client tools: keep tools, force tool_choice=none.

    Live full response 2026-08-18 morph-v3-large:
    - tool_choice auto/omit/required → HTTP 400 (no tool-call-parser)
    - tools + tool_choice none → 200 with XML in content:
      <tool_call>{"name":"bash","arguments":{...}}</tool_call>
    Proxy later converts that XML into OpenAI tool_calls.
    """
    out = dict(body)
    out["tool_choice"] = "none"
    if "max_tokens" not in out:
        mct = out.get("max_completion_tokens")
        if isinstance(mct, int) and mct > 0:
            out["max_tokens"] = mct
    out.pop("max_completion_tokens", None)
    out.pop("reasoning_effort", None)
    out.pop("reasoning", None)
    out.pop("thinking", None)
    out.pop("think", None)
    return out


def drop_pi_extras(body: dict) -> dict:
    out = dict(body)
    for key in _DROP_ALWAYS:
        out.pop(key, None)
    return out


def format_apply_xml(
    instruction: str,
    code: str,
    update: str,
) -> str:
    """Docs Message Format: instruction + code + update tags."""
    return (
        f"<instruction>{instruction}</instruction>\n"
        f"<code>{code}</code>\n"
        f"<update>{update}</update>"
    )


def collapse_apply_messages(messages: list) -> list[dict]:
    """Join texts into one Apply user blob (already-XML path)."""
    parts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        text = msg.get("content")
        if isinstance(text, str) and text.strip():
            parts.append(text)
    return [{
        "role": "user",
        "content": "\n\n".join(parts),
    }]


def wrap_chat_as_apply_xml(messages: list) -> list[dict]:
    """Map OpenAI chat turns → official Apply XML (one user message).

    Docs require a single user message with instruction/code/update.
    Live 2026-08-18 A/B on morph-v3-large:
    - user text in <update> → exact echo
    - prior turns in <code> → Morph returns the transcript dump
    - user task in <instruction>, empty <code>, chat <update> →
      conversational reply
    """
    systems: list[str] = []
    prior_lines: list[str] = []
    last_user = ""

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").strip().lower()
        text = msg.get("content")
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.strip()
        if role == "system":
            systems.append(text)
            continue
        if role == "user":
            if last_user:
                prior_lines.append(f"user: {last_user}")
            last_user = text
            continue
        if role == "assistant":
            prior_lines.append(f"assistant: {text}")
            continue

    instr_parts: list[str] = []
    if systems:
        instr_parts.append("\n\n".join(systems))
    if prior_lines:
        # Keep history in instruction, not <code> (code dump leaks).
        instr_parts.append(
            "Prior conversation:\n" + "\n".join(prior_lines[-8:]),
        )
    if last_user:
        instr_parts.append(
            "I will reply conversationally to the user message: "
            f"{last_user}"
        )
    else:
        instr_parts.append("I will reply conversationally to the user.")
    instruction = "\n\n".join(instr_parts)
    content = format_apply_xml(
        instruction,
        "",
        _APPLY_CHAT_UPDATE,
    )
    return [{"role": "user", "content": content}]


def wrap_chat_as_apply_fast(messages: list) -> list[dict]:
    """morph-v3-fast chat wrap: last user only, space code/update.

    Live 2026-08-18: this model emits system/developer text (Pi
    AGENTS.md) as the merged file. Do not put those turns in XML.
    """
    last_user = last_user_text(messages)
    if last_user:
        instruction = (
            "Reply conversationally to the user message: "
            f"{last_user}"
        )
    else:
        instruction = "Reply conversationally to the user."
    content = format_apply_xml(
        instruction,
        _APPLY_FAST_SLOT,
        _APPLY_FAST_SLOT,
    )
    return [{"role": "user", "content": content}]


def build_apply_messages(messages: list) -> list[dict]:
    """Always forward Apply as docs XML in one user message."""
    if looks_like_apply_payload(messages):
        return collapse_apply_messages(messages)
    return wrap_chat_as_apply_xml(messages)


def extract_xml_tool_calls(
    content: str,
) -> tuple[str | None, list[dict]]:
    """Parse Apply XML <tool_call> blocks → OpenAI tool_calls."""
    calls: list[dict] = []
    for index, match in enumerate(
        _TOOL_CALL_TAG_RE.finditer(content),
    ):
        raw = match.group(1).strip()
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        name = obj.get("name")
        if not name and isinstance(obj.get("function"), dict):
            name = obj["function"].get("name")
        if not isinstance(name, str) or not name:
            continue
        args = obj.get("arguments", obj.get("parameters", {}))
        if isinstance(args, dict):
            args_s = json.dumps(args, ensure_ascii=False)
        elif isinstance(args, str):
            args_s = args
        else:
            args_s = json.dumps(args, ensure_ascii=False)
        calls.append({
            "id": f"call-morph-{index}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": args_s,
            },
        })
    if not calls:
        return content, []
    remaining = _TOOL_CALL_TAG_RE.sub("", content).strip()
    return (remaining or None), calls


def unwrap_morph_apply_content(content: object) -> object:
    """Unwrap Morph Apply / XML-tagged assistant content for clients.

    Docs show plain merged file text. When upstream returns XML
    (``<reply>``, Apply envelope, lone ``<code>``), extract the
    payload. Plain text passes through unchanged.
    """
    if not isinstance(content, str):
        return content
    text = content.strip()
    if not text or "<" not in text:
        return content

    reply = _REPLY_TAG_RE.search(text)
    if reply and reply.group(1).strip():
        return reply.group(1).strip()

    lower = text.lower()
    has_code = "<code>" in lower
    has_apply = (
        "<instruction>" in lower
        or "<update>" in lower
    )
    if has_code and has_apply:
        code = _CODE_TAG_RE.search(text)
        if code and code.group(1).strip():
            return code.group(1).strip()

    if lower.startswith("<code>") and "</code>" in lower:
        code = _CODE_TAG_RE.search(text)
        if code:
            return code.group(1).strip()

    # Warp Grep may embed <think> in content; drop for chat clients.
    if "<think>" in lower:
        cleaned = _THINK_TAG_RE.sub("", text).strip()
        if cleaned:
            return cleaned
    return content


def _unwrap_message_block(block: dict) -> dict:
    out = dict(block)
    content = out.get("content")
    if isinstance(content, str) and "<tool_call>" in content.lower():
        remaining, calls = extract_xml_tool_calls(content)
        if calls:
            existing = out.get("tool_calls")
            if not (isinstance(existing, list) and existing):
                out["tool_calls"] = calls
            out["content"] = remaining
            return out
    if "content" in out:
        out["content"] = unwrap_morph_apply_content(out.get("content"))
    return out


def normalize_morph_completion(data: dict) -> dict:
    """Unwrap Apply XML tool_call / tags inside chat.completion JSON."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    choices = out.get("choices")
    if not isinstance(choices, list):
        return out
    new_choices: list = []
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        ch = dict(choice)
        msg = ch.get("message")
        if isinstance(msg, dict):
            unwrapped = _unwrap_message_block(msg)
            ch["message"] = unwrapped
            if unwrapped.get("tool_calls"):
                ch["finish_reason"] = "tool_calls"
        delta = ch.get("delta")
        if isinstance(delta, dict):
            ch["delta"] = _unwrap_message_block(delta)
        new_choices.append(ch)
    out["choices"] = new_choices
    return out


_BASH_TOOL_NAMES = frozenset({
    "bash",
    "shell",
    "run",
    "run_command",
})


def client_bash_tool_name(body: dict) -> str | None:
    tools = body.get("tools")
    if not isinstance(tools, list):
        return None
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function")
        if not isinstance(fn, dict):
            fn = tool
        name = fn.get("name")
        if isinstance(name, str) and name.lower() in _BASH_TOOL_NAMES:
            return name
    return None


_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(
    r"```(?:ba)?sh\s*(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_DOLLAR_RE = re.compile(r"^\$\s+(\S.*)$", re.MULTILINE)
_IDENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._+-]*$")
_SHELL_HINT_RE = re.compile(r"[|><;&`$()/\\]|\s-[A-Za-z0-9]")
_GREETINGS = frozenset({
    "hi", "hey", "hello", "halo", "hai", "ok", "yes", "no",
})
_PROSE_FIRST = frozenset({
    "sekarang", "sebelum", "jangan", "jika", "jawab",
    "dalam", "apakah", "bandingkan", "jelaskan",
    "tentukan", "jalankan", "please", "now", "then",
    "this", "that", "when", "what", "how", "why",
    "anda", "kamu", "saya", "untuk", "pada", "dari",
    "dengan", "lalu",
})


def _looks_like_command(text: str) -> bool:
    """True for a shell snippet, not a chat sentence."""
    raw = text.strip()
    if not raw or len(raw) > 4000:
        return False
    if raw.startswith(("#", "-", "*")):
        return False
    if raw.endswith(("?", ".", ":")):
        return False
    first = raw.split()[0]
    lowered = first.lower()
    if raw.lower() in _GREETINGS or lowered in _GREETINGS:
        return False
    if lowered in _PROSE_FIRST:
        return False
    if first.startswith(("./", "/", "$", "~")):
        return True
    if not _IDENT_RE.match(first):
        return False
    words = raw.split()
    if len(words) == 1:
        return True
    if _SHELL_HINT_RE.search(raw):
        return True
    second = words[1]
    if second.startswith(("-", "/", ".", "~")):
        return True
    if _IDENT_RE.match(second) and len(words) <= 12:
        return True
    return False


def _add_shell_candidate(found: list[str], seen: set[str], raw: str) -> None:
    item = raw.strip().strip("`")
    if item.startswith("$ "):
        item = item[2:].strip()
    if not _looks_like_command(item):
        return
    if item in seen:
        return
    seen.add(item)
    found.append(item)


def _user_shell_candidates(user: str) -> list[str]:
    """Command snippets the user asked to run (any shell command)."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _FENCE_RE.finditer(user):
        _add_shell_candidate(found, seen, match.group(1))
    for match in _BACKTICK_RE.finditer(user):
        _add_shell_candidate(found, seen, match.group(1))
    for match in _DOLLAR_RE.finditer(user):
        _add_shell_candidate(found, seen, match.group(1))
    for line in user.splitlines():
        _add_shell_candidate(found, seen, line)
    return found


def _morph_shell_payload(text: str) -> str | None:
    """Strip merge-file wrappers; keep a runnable shell payload."""
    raw = text.strip()
    fence = _FENCE_RE.search(raw)
    if fence:
        raw = fence.group(1).strip()
    raw = raw.strip("`")
    if (
        raw.startswith("(")
        and raw.endswith(")")
        and "\n" not in raw
        and len(raw) > 2
    ):
        raw = raw[1:-1].strip()
    lines = [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        return None
    if len(lines) == 1:
        payload = lines[0]
    else:
        payload = "\n".join(lines)
    head = payload.splitlines()[0]
    if not _looks_like_command(head):
        return None
    return payload


def _resolved_shell_command(text: str, user: str) -> str | None:
    """Map Morph merge output to the shell command the user requested."""
    wanted = _user_shell_candidates(user)
    if not wanted:
        return None
    payload = _morph_shell_payload(text)
    if payload:
        head = payload.splitlines()[0].strip()
        for item in wanted:
            if payload == item or head == item:
                return item
            if item in payload.splitlines():
                return item
        if len(wanted) == 1:
            return wanted[0]
    if _is_long_prompt_echo(text, user) and len(wanted) == 1:
        return wanted[0]
    return None


_ECHO_MIN = 80


def _is_long_prompt_echo(text: str, user: str) -> bool:
    """True when Morph copied a long user prompt (possibly truncated)."""
    if not text or not user or len(user) < _ECHO_MIN:
        return False
    if text == user:
        return True
    if user.startswith(text) and len(text) >= _ECHO_MIN:
        return True
    head = user[:_ECHO_MIN]
    if text.startswith(head) and len(text) >= _ECHO_MIN:
        return True
    return False


def apply_fast_client_output(
    content: object,
    *,
    last_user: str,
    bash_tool: str | None,
) -> tuple[dict, str]:
    """morph-v3-fast merge output → chat or a shell tool_call.

    Apply-fast emits merged file text. When the client sent a shell
    tool, any requested command (own line, backticks, fence, $ cmd)
    is converted to OpenAI tool_calls — not one hardcoded binary.
    Long prompt echoes are dropped unless they contain exactly one
    such command.
    """
    text = content.strip() if isinstance(content, str) else ""
    user = (last_user or "").strip()
    cmd = (
        _resolved_shell_command(text, user)
        if bash_tool
        else None
    )
    if cmd and bash_tool:
        args = json.dumps({"command": cmd}, ensure_ascii=False)
        return ({
            "content": None,
            "tool_calls": [{
                "id": "call-morph-0",
                "type": "function",
                "function": {
                    "name": bash_tool,
                    "arguments": args,
                },
            }],
        }, "tool_calls")
    if _is_long_prompt_echo(text, user):
        return {"content": None}, "stop"
    return (
        {"content": content if isinstance(content, str) else text},
        "stop",
    )


def apply_fast_completion(
    data: dict,
    *,
    last_user: str,
    bash_tool: str | None,
) -> dict:
    out = dict(data)
    choices = out.get("choices")
    if not isinstance(choices, list) or not choices:
        return out
    ch0 = choices[0]
    if not isinstance(ch0, dict):
        return out
    msg = ch0.get("message")
    if not isinstance(msg, dict):
        return out
    rewritten, finish = apply_fast_client_output(
        msg.get("content"),
        last_user=last_user,
        bash_tool=bash_tool,
    )
    new_msg = dict(msg)
    new_msg["content"] = rewritten.get("content")
    if rewritten.get("tool_calls"):
        new_msg["tool_calls"] = rewritten["tool_calls"]
    ch = dict(ch0)
    ch["message"] = new_msg
    ch["finish_reason"] = finish
    out["choices"] = [ch, *choices[1:]]
    return out


class MorphSseToolState:
    """Buffer streamed Apply <tool_call> XML across SSE deltas."""

    def __init__(self) -> None:
        self.buf: str = ""
        self.buffering: bool = False
        self.emitted: bool = False
        self.apply_fast: bool = False
        self.last_user: str = ""
        self.bash_tool: str | None = None
        self.content_buf: str = ""


def normalize_morph_sse_line(
    line: str,
    state: MorphSseToolState | None = None,
) -> str | None:
    """Rewrite SSE lines; buffer Apply XML tool_call until complete."""
    stripped = line.strip()
    if not stripped.startswith("data:"):
        return line
    payload = stripped[5:].strip()
    if not payload or payload == "[DONE]":
        return line
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return line
    if not isinstance(data, dict):
        return line

    if state is None:
        if any(
            isinstance(c, dict)
            and isinstance(
                ((c.get("delta") or c.get("message") or {}).get(
                    "content",
                )),
                str,
            )
            and "<" in str(
                (c.get("delta") or c.get("message") or {}).get(
                    "content",
                ),
            )
            for c in (data.get("choices") or [])
        ):
            fixed = normalize_morph_completion(data)
            return f"data: {json.dumps(fixed, ensure_ascii=False)}"
        return line

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return line
    choice0 = choices[0]
    if not isinstance(choice0, dict):
        return line
    delta = choice0.get("delta")
    if not isinstance(delta, dict):
        delta = {}
    piece = delta.get("content")
    finish = choice0.get("finish_reason")

    if state.apply_fast:
        if isinstance(piece, str) and piece:
            state.content_buf += piece
            if not finish:
                return None
        if not finish:
            return line
        rewritten, new_finish = apply_fast_client_output(
            state.content_buf,
            last_user=state.last_user,
            bash_tool=state.bash_tool,
        )
        state.content_buf = ""
        out = dict(data)
        ch = dict(choice0)
        if rewritten.get("tool_calls"):
            state.emitted = True
            ch["delta"] = {
                "role": delta.get("role") or "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "index": i,
                        "id": tc["id"],
                        "type": "function",
                        "function": tc["function"],
                    }
                    for i, tc in enumerate(rewritten["tool_calls"])
                ],
            }
            ch["finish_reason"] = "tool_calls"
        else:
            ch["delta"] = {
                "role": delta.get("role") or "assistant",
                "content": rewritten.get("content") or "",
            }
            ch["finish_reason"] = new_finish
        out["choices"] = [ch]
        return f"data: {json.dumps(out, ensure_ascii=False)}"

    if isinstance(piece, str) and piece:
        if not state.buffering:
            probe = (state.buf + piece).lstrip()
            if probe.startswith("<tool_call") or probe.startswith(
                "<TOOL_CALL",
            ):
                state.buffering = True
        if state.buffering:
            state.buf += piece
            if "</tool_call>" in state.buf.lower():
                remaining, calls = extract_xml_tool_calls(state.buf)
                state.buf = remaining or ""
                state.buffering = bool(state.buf.strip())
                if calls and not state.emitted:
                    state.emitted = True
                    out = dict(data)
                    ch = dict(choice0)
                    ch["delta"] = {
                        "role": delta.get("role") or "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "index": i,
                                "id": tc["id"],
                                "type": "function",
                                "function": tc["function"],
                            }
                            for i, tc in enumerate(calls)
                        ],
                    }
                    # OpenAI clients expect tool_calls finish here.
                    ch["finish_reason"] = "tool_calls"
                    out["choices"] = [ch]
                    return (
                        f"data: {json.dumps(out, ensure_ascii=False)}"
                    )
            # Still buffering incomplete XML — suppress raw piece.
            return None

    if finish and state.buf and not state.emitted:
        remaining, calls = extract_xml_tool_calls(state.buf)
        state.buf = ""
        if calls:
            state.emitted = True
            out = dict(data)
            ch = dict(choice0)
            ch["delta"] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "index": i,
                        "id": tc["id"],
                        "type": "function",
                        "function": tc["function"],
                    }
                    for i, tc in enumerate(calls)
                ],
            }
            ch["finish_reason"] = "tool_calls"
            out["choices"] = [ch]
            return f"data: {json.dumps(out, ensure_ascii=False)}"

    # After XML→tool_calls emit, Morph still sends finish=stop —
    # rewrite so clients (Pi) treat the turn as a tool call.
    if finish and state.emitted and finish == "stop":
        out = dict(data)
        ch = dict(choice0)
        ch["finish_reason"] = "tool_calls"
        out["choices"] = [ch]
        return f"data: {json.dumps(out, ensure_ascii=False)}"

    # Non-tool XML tags in a complete non-streamed-style chunk.
    content = delta.get("content")
    if isinstance(content, str) and "<" in content:
        fixed = normalize_morph_completion(data)
        return f"data: {json.dumps(fixed, ensure_ascii=False)}"
    return line


def finalize_apply_body(body: dict) -> dict:
    """Keep only official Apply request fields.

    Maps OpenAI max_completion_tokens → max_tokens when needed.
    Docs default temperature is 0 when omitted.
    """
    out: dict = {}
    for key in _APPLY_KEYS:
        if key in body:
            out[key] = body[key]
    if "max_tokens" not in out:
        mct = body.get("max_completion_tokens")
        if isinstance(mct, int) and mct > 0:
            out["max_tokens"] = mct
    if "temperature" not in out:
        out["temperature"] = 0
    return out


def sanitize_morph_chat_body(body: dict) -> dict:
    """Full Morph request sanitize (called from prepare_request)."""
    model = body.get("model")
    apply = is_apply_model(model)
    warp = is_warp_grep_model(model)

    messages = body.get("messages")
    if not isinstance(messages, list):
        out = drop_pi_extras(body)
        if apply and client_has_tools(out):
            return prepare_apply_tools_body(out)
        if apply:
            return finalize_apply_body(strip_client_tools(out))
        if warp:
            return strip_client_tools(out)
        return sanitize_morph_tools(out)

    cleaned = [normalize_message(m) for m in messages]
    out = drop_pi_extras({**body, "messages": cleaned})

    if apply:
        if model_tail(model) == "morph-v3-fast":
            if looks_like_apply_last_user(cleaned):
                msgs = [{
                    "role": "user",
                    "content": last_user_text(cleaned),
                }]
            else:
                msgs = wrap_chat_as_apply_fast(cleaned)
            return finalize_apply_body(
                strip_client_tools({**out, "messages": msgs}),
            )
        if client_has_tools(out):
            # Agent tool turn — do not wrap as merge XML; keep tools.
            return prepare_apply_tools_body(out)
        msgs = build_apply_messages(cleaned)
        return finalize_apply_body(
            strip_client_tools({**out, "messages": msgs}),
        )

    if warp:
        return strip_client_tools(out)
    return sanitize_morph_tools(out)
