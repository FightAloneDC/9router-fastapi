"""Unit tests for scripts/agent_farm helpers and command builders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_farm.common import (  # noqa: E402
    DEFAULT_OUT_DIR,
    KEY_ENV,
    classify_error,
    farm_models,
    is_retryable,
    job_dirs,
    select_farm_models,
    strip_v1,
)
from agent_farm.agents.claude import ClaudeAgent  # noqa: E402
from agent_farm.agents.codex import patch_codex_wire_api  # noqa: E402
from agent_farm.agents.commandcode import make_commandcode  # noqa: E402
from agent_farm.agents.copilot import CopilotAgent  # noqa: E402
from agent_farm.agents.crush import CrushAgent  # noqa: E402
from agent_farm.agents.cursor_agent import make_cursor  # noqa: E402
from agent_farm.agents.hermes import HermesAgent  # noqa: E402
from agent_farm.agents.kimi import (  # noqa: E402
    KimiAgent,
    ensure_model_context,
)
from agent_farm.agents.reasonix import reasonix_provider_name  # noqa: E402
from agent_farm.agents.cline import ClineAgent  # noqa: E402
from agent_farm.agents import all_plugins  # noqa: E402
from agent_farm.runner import (  # noqa: E402
    decode_pipe,
    print_status,
    run_cmd,
    sanitize_status_line,
)


def test_farm_models_groups_and_skips_embeddings() -> None:
    grouped = farm_models(
        [
            "gcli/grok-4.6",
            "qd/auto",
            "mi/mistral-small-latest",
            "alims-intl/qwen3.7-flash",
            "mi/mistral-embed",
        ]
    )
    assert grouped["grok-cli"] == ["gcli/grok-4.6"]
    assert grouped["qoder"] == ["qd/auto"]
    assert grouped["mistral"] == ["mi/mistral-small-latest"]
    assert grouped["alibaba-studio"] == ["alims-intl/qwen3.7-flash"]


def test_select_farm_models_one_per_farm() -> None:
    grouped = {
        "mistral": ["mi/a", "mi/b"],
        "qoder": ["qd/a", "qd/b"],
        "grok-cli": [],
    }
    selected = select_farm_models(
        grouped,
        {"mistral", "qoder", "grok-cli"},
        one_per_farm=True,
    )
    assert selected == {"mistral": ["mi/a"], "qoder": ["qd/a"]}


def test_job_dirs_are_absolute(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out_dir, job_cwd = job_dirs(
        Path("runs"),
        "hermes",
        "mistral",
        "mi/mistral-small-latest",
    )
    assert out_dir.is_absolute()
    assert job_cwd.is_absolute()
    assert job_cwd == out_dir / "workspace"
    assert out_dir.name == "mi_mistral-small-latest"


def test_classify_error_and_retryable() -> None:
    assert classify_error("directory not found: foo", 1) == "path"
    assert classify_error("HTTP 429 rate_limited", 1) == "rate_limit"
    assert classify_error("TIMEOUT after 10s", -9) == "timeout"
    assert classify_error("500 Internal Server Error", 1) == "upstream"
    assert classify_error("boom", 1) == "exit"
    assert is_retryable("Rate limit exceeded")
    assert not is_retryable("directory not found")


def test_farm_output_stays_under_scratch() -> None:
    assert DEFAULT_OUT_DIR == Path(".scratch/farm")


def test_strip_v1() -> None:
    assert strip_v1("http://localhost:8013/v1") == "http://localhost:8013"
    assert strip_v1("http://localhost:8013/") == "http://localhost:8013"


def test_hermes_and_crush_cmds_use_work_dir(tmp_path: Path) -> None:
    work = (tmp_path / "ws").resolve()
    work.mkdir()
    hermes = HermesAgent().build_cmds(
        "mi/mistral-small-latest",
        ["P1", "P2"],
        work,
        "key",
        "sid",
    )
    assert str(work) in hermes[0]
    assert "--continue" in hermes[1]
    assert "--source" in hermes[0]
    assert "--ignore-user-config" in hermes[0]
    assert "--reasoning" not in hermes[0]
    grok = HermesAgent().build_cmds(
        "gcli/grok-4.5",
        ["P1"],
        work,
        "key",
        "sid",
    )
    assert "--reasoning" not in grok[0]
    crush = CrushAgent().build_cmds(
        "mi/mistral-small-latest",
        ["P1", "P2"],
        work,
        "key",
        "sid",
    )
    assert "--cwd" in crush[0]
    assert str(work) in crush[0]
    assert "--data-dir" in crush[0]
    cline = ClineAgent().build_cmds(
        "mi/x", ["P1", "P2"], work, "k", "sid",
    )
    assert "--json" in cline[0]
    assert "--id" not in cline[0]
    assert "--id" in cline[1]
    assert "--continue" in crush[1]


def test_claude_uses_messages_base_and_is_runnable() -> None:
    plugin = ClaudeAgent()
    assert plugin.supports_custom_openai
    assert not plugin.skip_reason
    env = plugin.extra_env(
        "key",
        "http://localhost:8013/v1",
        "mi/mistral-small-latest",
    )
    assert env["ANTHROPIC_BASE_URL"] == "http://localhost:8013"
    assert env["ANTHROPIC_API_KEY"] == "key"
    cmds = plugin.build_cmds(
        "mi/mistral-small-latest",
        ["P1", "P2"],
        Path("/tmp/ws"),
        "key",
        "sid",
    )
    assert cmds[0][0] == "claude"
    assert "-p" in cmds[0]
    assert "--continue" in cmds[1]


def test_claude_backup_replace_restore(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(KEY_ENV, "farm-key")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    settings.write_text(
        '{"env":{"ANTHROPIC_BASE_URL":'
        '"https://api.deepseek.com/anthropic",'
        '"ANTHROPIC_MODEL":"deepseek-v4-flash"},'
        '"permissions":{"deny":["Bash(sudo:*)"]}}\n'
    )
    plugin = ClaudeAgent()
    plugin.home = tmp_path
    plugin.prepare(
        "http://localhost:8013/v1",
        ["gcli/grok-4.5"],
    )
    farm = json.loads(settings.read_text())
    assert farm["env"]["ANTHROPIC_BASE_URL"] == (
        "http://localhost:8013"
    )
    assert farm["env"]["ANTHROPIC_MODEL"] == "gcli/grok-4.5"
    assert farm["permissions"]["deny"] == ["Bash(sudo:*)"]
    bak = claude_dir / "settings.json.9router-farm.bak"
    assert bak.is_file()
    old = json.loads(bak.read_text())
    assert "deepseek" in old["env"]["ANTHROPIC_BASE_URL"]
    plugin.teardown()
    restored = json.loads(settings.read_text())
    assert restored["env"]["ANTHROPIC_MODEL"] == "deepseek-v4-flash"
    assert not bak.exists()


def test_patch_codex_wire_api_chat_to_responses() -> None:
    raw = (
        "[model_providers.other]\n"
        'wire_api = "chat"\n'
        "[model_providers.fastapi_9router_8013]\n"
        'base_url = "http://localhost:8013/v1"\n'
        'wire_api = "chat"\n'
        "[profiles.default]\n"
        'model = "x"\n'
    )
    out, changed = patch_codex_wire_api(raw)
    assert changed
    assert 'fastapi_9router_8013]\nbase_url' in out
    farm = out.split("[model_providers.fastapi_9router_8013]")[1]
    farm = farm.split("[")[0]
    assert 'wire_api = "responses"' in farm
    assert 'wire_api = "chat"' in out.split(
        "[model_providers.fastapi_9router_8013]"
    )[0]


def test_sanitize_status_line_strips_cr_and_ansi() -> None:
    raw = "\r\x1b[32mOK\x1b[0m line\r\nnext"
    assert sanitize_status_line(raw) == "OK line next"


def test_print_status_starts_at_column_zero(
    capsys,
) -> None:
    print_status("hello\rworld")
    assert capsys.readouterr().out == "hello world\n"


def test_run_cmd_child_has_no_controlling_tty(
    tmp_path: Path,
) -> None:
    code, out, err = run_cmd(
        [
            "python3",
            "-c",
            (
                "import os\n"
                "try:\n"
                "    os.open('/dev/tty', os.O_RDWR)\n"
                "    print('TTY_OK')\n"
                "except OSError:\n"
                "    print('TTY_FAIL')\n"
            ),
        ],
        cwd=str(tmp_path),
        env=dict(**__import__("os").environ),
        timeout=10,
        need_pty=False,
    )
    assert code == 0
    assert "TTY_FAIL" in out
    del err


def test_run_cmd_pty_makes_stdout_a_tty(tmp_path: Path) -> None:
    assert ClineAgent().needs_pty
    code, out, err = run_cmd(
        [
            "python3",
            "-c",
            "import sys; print(sys.stdout.isatty())",
        ],
        cwd=str(tmp_path),
        env=dict(**__import__("os").environ),
        timeout=10,
        need_pty=True,
    )
    assert code == 0
    assert "True" in out
    del err


def test_new_agents_build_cmds(tmp_path: Path) -> None:
    work = (tmp_path / "ws").resolve()
    work.mkdir()
    cmd = make_commandcode("cmd", "cmd")
    argv = cmd.build_cmds("mi/x", ["P1", "P2"], work, "k", "sid")
    assert argv[0][0] == "cmd"
    assert "-p" in argv[0]
    assert "--continue" in argv[1]
    env = CopilotAgent().extra_env("k", "http://localhost:8013/v1", "m")
    assert env["COPILOT_PROVIDER_BASE_URL"].endswith("/v1")
    cur = make_cursor("cursor-agent", "cursor-agent")
    c0 = cur.build_cmds("m", ["P1"], work, "k", "sid")[0]
    assert c0[0] == "cursor-agent"
    assert "--endpoint" in c0
    assert reasonix_provider_name("mi/x") == "fastapi-9router-mi-x"


def test_user_binaries_are_registered() -> None:
    listed = {p.name: p for p in all_plugins()}
    for need in (
        "cmd",
        "copilot",
        "kilo",
        "kimi",
        "mimo",
        "opencode",
        "pi",
        "reasonix",
        "aider",
        "claude",
        "crush",
        "grok",
        "hermes",
        "qwen",
        "vibe",
        "cline",
        "codex",
    ):
        assert need in listed, need
        assert listed[need].supports_custom_openai, need
        assert not listed[need].skip_reason, need
    aliases = {
        "cmdc": "alias of cmd",
        "command-code": "alias of cmd",
        "commandcode": "alias of cmd",
        "kilocode": "alias of kilo",
        "agent": "alias of cursor-agent",
        "cursor": "alias of cursor-agent",
        "kiro-cli-chat": "alias of kiro-cli",
    }
    for name, reason in aliases.items():
        assert listed[name].skip_reason == reason
    assert listed["agy"].skip_reason
    assert listed["kimchi"].skip_reason
    assert listed["droid"].skip_reason
    assert listed["kiro-cli"].skip_reason
    assert listed["vibe-acp"].skip_reason
    assert listed["vibe-app-server"].skip_reason
    assert listed["kiro-cli-term"].skip_reason
    assert listed["cursor-agent"].skip_reason
    assert listed["qodercli"].skip_reason
    assert listed["zero"].skip_reason
    assert not listed["cursor-agent"].supports_custom_openai
    assert not listed["qodercli"].supports_custom_openai


def test_kimi_ensure_writes_max_context_size(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    cfg = home / ".kimi-code" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        '[models."fastapi-9router/mi/codestral-latest"]\n'
        'provider = "fastapi-9router"\n'
        'model = "mi/codestral-latest"\n'
        'capabilities = [ "tool_use" ]\n'
    )
    monkeypatch.setattr("agent_farm.agents.kimi.HOME", home)
    result = KimiAgent().ensure(
        "http://localhost:8013/v1",
        ["mi/codestral-latest", "mi/mistral-small-latest"],
    )
    text = cfg.read_text()
    assert result["ok"]
    assert "max_context_size = 256000" in text
    codestral = text.split(
        '[models."fastapi-9router/mi/codestral-latest"]', 1,
    )[1].split("\n[")[0]
    assert "max_context_size" in codestral
    assert "mistral-small-latest" in text


def test_ensure_model_context_is_idempotent() -> None:
    raw = (
        '[models."fastapi-9router/mi/x"]\n'
        "max_context_size = 128000\n"
    )
    out, changed = ensure_model_context(raw, "mi/x")
    assert changed is False
    assert out == raw


def test_decode_pipe_accepts_bytes() -> None:
    assert decode_pipe(None) == ""
    assert decode_pipe("ok") == "ok"
    assert decode_pipe(b"ok") == "ok"
    assert decode_pipe(b"\xff") == "\ufffd"


def test_timeout_bytes_concat_does_not_raise() -> None:
    import subprocess

    from agent_farm.runner import timeout_outputs

    exc = subprocess.TimeoutExpired(
        cmd=["pi"],
        timeout=1,
        output=b"stdout-bytes",
        stderr=b"stderr-bytes",
    )
    stdout, stderr = timeout_outputs(exc, 1)
    assert stdout == "stdout-bytes"
    assert "stderr-bytes" in stderr
    assert "TIMEOUT after 1s" in stderr
