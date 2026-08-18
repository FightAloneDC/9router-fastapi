"""Morph request adapter — cases from docs + request_details logs."""

import asyncio
import json

from app.providers.morph.config import MorphConfig
from app.providers.morph.handler import (
    MorphHandler,
    adapt_morph_body,
    flatten_content,
)


def test_flatten_list_parts() -> None:
    assert flatten_content([
        {"type": "text", "text": "hello "},
        {"type": "text", "text": "world"},
    ]) == "hello world"


def test_flatten_string_passthrough() -> None:
    assert flatten_content("plain") == "plain"


def test_flatten_none() -> None:
    assert flatten_content(None) is None


def test_adapt_flattens_agent_parts() -> None:
    body = adapt_morph_body({
        "model": "morph-qwen36-27b",
        "messages": [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "You are a bot."},
                ],
            },
            {"role": "user", "content": "hi"},
        ],
    })
    assert body["messages"][0]["content"] == "You are a bot."
    assert body["messages"][1]["content"] == "hi"
    assert len(body["messages"]) == 2


def test_apply_xml_collapses_to_one_user_string() -> None:
    """Official Apply shape already present: one user; no tools."""
    xml = (
        "<instruction>add null check</instruction>\n"
        "<code>def f(x):\n  return x</code>\n"
        "<update>def f(x):\n  if x is None: return\n"
        "  return x</update>"
    )
    body = adapt_morph_body({
        "model": "mo/morph-v3-large",
        "messages": [
            {"role": "system", "content": "hint"},
            {"role": "user", "content": xml},
        ],
        "top_p": 0.9,
    })
    assert set(body.keys()) <= {
        "model", "messages", "stream", "max_tokens", "temperature",
    }
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"
    content = body["messages"][0]["content"]
    assert "hint" in content
    assert "<instruction>" in content
    assert "<code>" in content
    assert "<update>" in content
    assert "tools" not in body
    assert "top_p" not in body


def test_apply_wraps_pi_chat_as_docs_xml() -> None:
    """Chat without tools → docs instruction/code/update wrap.

    Live: user text in <update> echoes; user text in <instruction>
    with update marker chats normally. Agent turns with tools use
    the tools path (see test_apply_keeps_tools_forces_tool_choice_none).
    """
    prompt = "pagi kawan, lagi apa nih?"
    body = adapt_morph_body({
        "model": "mo/morph-v3-large",
        "messages": [
            {
                "role": "developer",
                "content": (
                    "You are an expert coding assistant operating "
                    "inside pi. Extensions: pi-mcp-adapter, "
                    "pi-subagents, pi-web-access."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": 8192,
        "reasoning_effort": "medium",
        "store": False,
        "stream": True,
    })
    assert set(body.keys()) <= {
        "model", "messages", "stream", "max_tokens", "temperature",
    }
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"
    content = body["messages"][0]["content"]
    assert content.startswith("<instruction>")
    assert "<code>" in content
    assert "<update>" in content
    assert "pi-mcp-adapter" in content
    assert prompt in content
    assert "(no file edit; reply as chat)" in content
    assert f"<update>{prompt}</update>" not in content
    assert body["max_tokens"] == 8192
    assert body["stream"] is True
    assert "tools" not in body
    assert "store" not in body
    assert "reasoning_effort" not in body


def test_apply_wraps_user_only_as_docs_xml() -> None:
    """/chat user-only still becomes official Apply XML."""
    prompt = "pagi kawan, lagi apa nih?"
    body = adapt_morph_body({
        "model": "morph-v3-large",
        "messages": [{"role": "user", "content": prompt}],
    })
    assert len(body["messages"]) == 1
    content = body["messages"][0]["content"]
    assert "<instruction>" in content
    assert "<code>" in content
    assert "<update>" in content
    assert prompt in content
    assert "(no file edit; reply as chat)" in content
    assert body["temperature"] == 0


def test_apply_wraps_multi_turn_history_in_instruction() -> None:
    """Prior turns stay in <instruction>; <code> stays empty."""
    body = adapt_morph_body({
        "model": "mo/morph-v3-large",
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hi!"},
            {"role": "user", "content": "2 x 2 = ?"},
        ],
    })
    assert len(body["messages"]) == 1
    content = body["messages"][0]["content"]
    assert "You are helpful." in content
    assert "2 x 2 = ?" in content
    assert "user: hi" in content
    assert "assistant: hi!" in content
    assert "<code></code>" in content
    assert "(no file edit; reply as chat)" in content


def test_unwrap_apply_xml_reply_and_code() -> None:
    from app.providers.morph.transform import (
        normalize_morph_completion,
        unwrap_morph_apply_content,
    )

    assert unwrap_morph_apply_content(
        "<reply>Pagi kawan!</reply>",
    ) == "Pagi kawan!"
    assert unwrap_morph_apply_content(
        "<instruction>x</instruction>\n"
        "<code>def f():\n  return 1</code>\n"
        "<update>y</update>",
    ) == "def f():\n  return 1"
    assert unwrap_morph_apply_content("plain merge") == "plain merge"

    data = normalize_morph_completion({
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "<reply>ok</reply>",
            },
        }],
    })
    assert data["choices"][0]["message"]["content"] == "ok"


def test_chat_date_prompt_wrapped_as_apply_xml() -> None:
    """request_details id=5108: /chat date prompt → Apply XML."""
    prompt = (
        "Sebelum menjawab, tentukan tanggal saat ini berdasarkan "
        "informasi waktu yang tersedia di environment/session ini."
    )
    body = adapt_morph_body({
        "model": "mo/morph-v3-large",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "temperature": 1,
        "max_tokens": 4096,
    })
    assert len(body["messages"]) == 1
    content = body["messages"][0]["content"]
    assert "<instruction>" in content
    assert prompt in content
    assert body["temperature"] == 1
    assert body["max_tokens"] == 4096


def test_warp_grep_strips_client_tools_keeps_turns() -> None:
    body = adapt_morph_body({
        "model": "morph-warp-grep-v2.1",
        "messages": [
            {"role": "user", "content": "<search_string>auth</search_string>"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call_1", "function": {"name": "grep_search"}},
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "hits",
            },
        ],
        "tools": [{"type": "function", "function": {"name": "nope"}}],
        "tool_choice": "auto",
    })
    assert "tools" not in body
    assert "tool_choice" not in body
    assert body["messages"][1]["tool_calls"][0]["id"] == "call_1"
    assert body["messages"][2]["tool_call_id"] == "call_1"


def test_apply_keeps_tools_forces_tool_choice_none() -> None:
    """Live: Apply+tools+none → <tool_call> XML; auto/omit → 400."""
    tools = [{
        "type": "function",
        "function": {
            "name": "bash",
            "parameters": {"type": "object"},
        },
    }]
    body = adapt_morph_body({
        "model": "mo/morph-v3-large",
        "messages": [
            {"role": "developer", "content": "You are pi"},
            {"role": "user", "content": "run date"},
        ],
        "tools": tools,
        "tool_choice": "auto",
        "stream": True,
    })
    assert body["tools"] == tools
    assert body["tool_choice"] == "none"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["content"] == "run date"
    # Must NOT wrap agent tool turns as merge XML.
    assert "<instruction>" not in body["messages"][1]["content"]
    assert body["messages"][0]["content"] == "You are pi"


def test_unwrap_apply_xml_tool_call_to_openai() -> None:
    from app.providers.morph.transform import normalize_morph_completion

    raw = (
        '<tool_call>\n'
        '{"name": "bash", "arguments": {"command": "date"}}\n'
        "</tool_call>"
    )
    data = normalize_morph_completion({
        "choices": [{
            "message": {
                "role": "assistant",
                "content": raw,
                "tool_calls": [],
            },
        }],
    })
    msg = data["choices"][0]["message"]
    assert msg["content"] is None
    assert msg["tool_calls"][0]["function"]["name"] == "bash"
    assert "date" in msg["tool_calls"][0]["function"]["arguments"]
    assert data["choices"][0]["finish_reason"] == "tool_calls"


def test_fast_model_keeps_tools_on_auto() -> None:
    """Fast Models must keep tools even when tool_choice is auto."""
    tools = [{
        "type": "function",
        "function": {"name": "bash", "description": "run"},
    }]
    body = adapt_morph_body({
        "model": "morph-qwen36-27b",
        "messages": [{"role": "user", "content": "hi"}],
        "tool_choice": "auto",
        "tools": tools,
        "parallel_tool_calls": True,
    })
    assert body["tool_choice"] == "auto"
    assert body["tools"] == tools


def test_drops_tool_choice_auto_and_tools() -> None:
    """Legacy name: Fast Models no longer strip auto tools."""
    tools = [{
        "type": "function",
        "function": {"name": "bash", "description": "run"},
    }]
    body = adapt_morph_body({
        "model": "morph-qwen36-27b",
        "messages": [{"role": "user", "content": "hi"}],
        "tool_choice": "auto",
        "tools": tools,
        "parallel_tool_calls": True,
    })
    assert body["tools"] == tools
    assert body["tool_choice"] == "auto"


def test_drops_tools_when_tool_choice_omitted() -> None:
    """Apply + tools without choice → keep tools, force none."""
    body = adapt_morph_body({
        "model": "mo/morph-v3-large",
        "messages": [
            {"role": "developer", "content": "You are pi"},
            {"role": "user", "content": "hi"},
        ],
        "tools": [{
            "type": "function",
            "function": {"name": "bash", "parameters": {"type": "object"}},
        }],
        "stream": True,
    })
    assert body["tools"]
    assert body["tool_choice"] == "none"
    assert body["messages"][1]["content"] == "hi"


def test_keeps_tool_choice_required() -> None:
    body = adapt_morph_body({
        "model": "morph-kimik3",
        "messages": [{"role": "user", "content": "hi"}],
        "tool_choice": "required",
        "tools": [{"type": "function", "function": {"name": "f"}}],
    })
    assert body["tool_choice"] == "required"


def test_fast_model_keeps_tools() -> None:
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
        },
    }]
    body = adapt_morph_body({
        "model": "morph-qwen36-27b",
        "messages": [
            {"role": "user", "content": "call the function"},
        ],
        "tool_choice": "none",
        "tools": tools,
        "parallel_tool_calls": True,
    })
    assert body["tool_choice"] == "none"
    assert body["tools"] == tools
    assert body["parallel_tool_calls"] is True


def test_kimi_omits_null_content_when_tools() -> None:
    body = adapt_morph_body({
        "model": "morph-kimik3",
        "messages": [
            {
                "role": "system",
                "content": None,
                "tools": [{"type": "function", "function": {}}],
            },
        ],
        "tool_choice": "required",
    })
    assert "content" not in body["messages"][0]
    assert body["messages"][0]["tools"]
    assert body["tool_choice"] == "required"


def test_prepare_request_and_no_farm_rotate() -> None:
    handler = MorphHandler(MorphConfig())
    _h, body = asyncio.run(handler.prepare_request(
        {},
        {
            "model": "morph-v3-fast",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "x"}],
                },
            ],
        },
    ))
    assert len(body["messages"]) == 1
    content = body["messages"][0]["content"]
    assert "<instruction>" in content
    assert "User: x" not in content
    assert "x" in content
    assert "<code> </code>" in content
    assert "<update> </update>" in content
    assert "(no file edit; reply as chat)" not in content
    err = (
        '{"error":{"message":"text.charCodeAt is not a function"'
        ',"type":"internal_error"}}'
    )
    assert handler.should_fallback_on_error(500, err) is False
    assert handler.should_fallback_on_error(429, "retry") is None


def test_morph_v3_fast_chat_does_not_forward_system() -> None:
    """Live: Pi AGENTS.md in system is emitted as the merged file."""
    marker = "UNIQUE_AGENTS_MARKER_9ROUTER"
    body = adapt_morph_body({
        "model": "mo/morph-v3-fast",
        "messages": [
            {
                "role": "developer",
                "content": f"# AGENTS.md\n{marker}\nThink Before Coding.",
            },
            {"role": "user", "content": "hi"},
        ],
        "tools": [{
            "type": "function",
            "function": {"name": "bash"},
        }],
    })
    assert "tools" not in body
    assert len(body["messages"]) == 1
    content = body["messages"][0]["content"]
    assert marker not in content
    assert "AGENTS.md" not in content
    assert "hi" in content
    assert content.startswith("<instruction>")
    assert "<code> </code>" in content
    assert "<update> </update>" in content


def test_morph_v3_fast_real_apply_xml_still_collapses() -> None:
    xml = (
        "<instruction>merge</instruction>\n"
        "<code>a=1</code>\n"
        "<update>a=2</update>"
    )
    body = adapt_morph_body({
        "model": "mo/morph-v3-fast",
        "messages": [
            {"role": "system", "content": "# AGENTS.md dumped"},
            {"role": "user", "content": xml},
        ],
    })
    content = body["messages"][0]["content"]
    assert "<code>a=1</code>" in content
    assert "Reply conversationally" not in content
    assert "AGENTS.md" not in content


def test_morph_v3_large_tools_still_passthrough() -> None:
    """large stays on the tools+none path; do not wrap."""
    body = adapt_morph_body({
        "model": "mo/morph-v3-large",
        "messages": [
            {"role": "developer", "content": "# AGENTS.md"},
            {"role": "user", "content": "hi"},
        ],
        "tools": [{
            "type": "function",
            "function": {"name": "bash"},
        }],
    })
    assert body["tools"]
    assert body["tool_choice"] == "none"
    assert body["messages"][1]["content"] == "hi"


def _run_prompt(cmd: str) -> str:
    return (
        "Jalankan perintah berikut di environment ini.\n"
        f"\n{cmd}\n\n"
        "Bandingkan outputnya dengan jawaban sebelumnya."
    )


def _assert_bash_cmd(msg: dict, finish: str, cmd: str) -> None:
    assert msg.get("content") is None
    calls = msg.get("tool_calls") or []
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "bash"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["command"] == cmd
    assert finish == "tool_calls"


def test_apply_fast_drops_echo_of_user_prompt() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    prompt = (
        "Sebelum menjawab, baca konteks environment/session ini.\n"
        "Jangan mengarang fakta yang tidak ada di context.\n"
        "Jawab hanya:\n- Ringkasan:\n- Sumber:\n- Catatan:"
    )
    msg, finish = apply_fast_client_output(
        prompt,
        last_user=prompt,
        bash_tool="bash",
    )
    assert msg.get("content") in (None, "")
    assert not msg.get("tool_calls")
    assert finish == "stop"


def test_apply_fast_drops_truncated_echo() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    prompt = (
        "Sebelum menjawab, baca konteks environment/session ini "
        "berdasarkan informasi yang tersedia di session.\n"
        "Jangan mengarang fakta yang tidak ada di context.\n"
        "Jawab hanya:\n- Ringkasan:\n- Sumber:\n- Catatan:"
    )
    msg, finish = apply_fast_client_output(
        prompt[:120],
        last_user=prompt,
        bash_tool="bash",
    )
    assert msg.get("content") in (None, "")
    assert finish == "stop"


def test_apply_fast_keeps_short_hi() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    msg, finish = apply_fast_client_output(
        "hi",
        last_user="hi",
        bash_tool="bash",
    )
    assert msg.get("content") == "hi"
    assert finish == "stop"


def test_apply_fast_ls_line_becomes_tool_call() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    prompt = _run_prompt("ls -la")
    msg, finish = apply_fast_client_output(
        "ls -la",
        last_user=prompt,
        bash_tool="bash",
    )
    _assert_bash_cmd(msg, finish, "ls -la")


def test_apply_fast_git_status_from_backticks() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    prompt = "Cek status repo dengan `git status` lalu jelaskan."
    msg, finish = apply_fast_client_output(
        "git status",
        last_user=prompt,
        bash_tool="bash",
    )
    _assert_bash_cmd(msg, finish, "git status")


def test_apply_fast_curl_from_script_wrap() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    cmd = "curl -sS https://example.com/health"
    prompt = _run_prompt(cmd)
    script = (
        "#!/bin/bash\n"
        "# fetch health endpoint\n"
        f"{cmd}\n"
    )
    msg, finish = apply_fast_client_output(
        script,
        last_user=prompt,
        bash_tool="bash",
    )
    _assert_bash_cmd(msg, finish, cmd)


def test_apply_fast_echo_with_one_command_becomes_tool_call() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    prompt = _run_prompt("uname -a")
    msg, finish = apply_fast_client_output(
        prompt,
        last_user=prompt,
        bash_tool="bash",
    )
    _assert_bash_cmd(msg, finish, "uname -a")


def test_apply_fast_dollar_prompt() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    prompt = "Lihat proses dengan:\n$ ps aux | head\n"
    msg, finish = apply_fast_client_output(
        "ps aux | head",
        last_user=prompt,
        bash_tool="bash",
    )
    _assert_bash_cmd(msg, finish, "ps aux | head")


def test_apply_fast_keeps_normal_reply() -> None:
    from app.providers.morph.transform import apply_fast_client_output

    msg, finish = apply_fast_client_output(
        "17 dikali 3 adalah 51.",
        last_user="Berapa 17 dikali 3?",
        bash_tool="bash",
    )
    assert msg.get("content") == "17 dikali 3 adalah 51."
    assert not msg.get("tool_calls")
    assert finish == "stop"
