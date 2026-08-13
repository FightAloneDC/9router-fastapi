# Agent Farm

Farm-test **real agent CLIs** against 9Router (`http://localhost:8013/v1`) using custom OpenAI-compatible providers.

This is not a curl “say hi” probe. Each job runs **3 prompts in one session** via subprocess, with optional concurrency.

## Layout

```text
scripts/agent_farm_chat_test.py   # thin entry point
scripts/agent_farm/
  README.md                       # this file
  common.py                       # API key, model discovery, IO helpers
  runner.py                       # CLI + ThreadPoolExecutor runner
  registry.py                     # re-exports agent registry
  agents/
    _base.py                      # AgentPlugin / StubAgent
    hermes.py                     # one file = one agent
    pi.py
    aider.py
    ...
    __init__.py                   # register RUN + SKIP stubs
```

## Prerequisites

1. 9Router reachable at `http://localhost:8013` (or pass `--base-url`).
2. API key available as env `HERMES_CUSTOM_LOCALHOST_8013_API_KEY`
   (also read from `~/.hermes/.env` if unset).
3. Target agent binaries on `PATH`.

```bash
set -a
source ~/.hermes/.env
set +a
```

## Quick start

From the **repo root**:

```bash
# List registered agents (RUN = farm-wired, SKIP = stub / unsupported)
python3 scripts/agent_farm_chat_test.py --list

# Merge custom provider into agent configs only (serial, safe merge)
python3 scripts/agent_farm_chat_test.py --ensure-only

# Dry-run: write command meta, do not exec agents
python3 scripts/agent_farm_chat_test.py --dry-run --skip-ensure \
  --agents hermes,pi \
  --models 'mi/mistral-small-latest,qd/qoder/auto'

# Probe: smoke-test every runnable agent (1 prompt, 1 model/farm)
python3 scripts/agent_farm_chat_test.py --probe --max-workers 2

# Full farm (180s per turn by default)
python3 scripts/agent_farm_chat_test.py --max-workers 2 \
  --out-dir .scratch/farm
```

## CLI flags

| Flag | Meaning |
|------|---------|
| `--list` | Print registry and exit |
| `--ensure-only` | Only merge provider configs |
| `--skip-ensure` | Do not touch agent config files |
| `--dry-run` | Write `meta.json` / cmds only |
| `--agents a,b` | Subset of runnable agents |
| `--farms …` | Default: `grok-cli,alibaba-studio,qoder,mistral` |
| `--models id,id` | Explicit model ids (skips farm filter) |
| `--max-workers N` | Concurrent sessions (default `2`) |
| `--timeout SEC` | Per-turn kill; default `180`. `0` = none |
| `--retries N` | Extra attempts per turn on HTTP 429 (default `2`) |
| `--one-per-farm` | First model only from each farm |
| `--probe` | Smoke test: 1 prompt + `--one-per-farm` |
| `--out-dir PATH` | Output root (default `.scratch/farm`) |
| `--prompt-file PATH` | JSON list of prompt strings |
| `--base-url URL` | OpenAI base (default `http://localhost:8013/v1`) |

## What a run does

1. **Ensure (serial)** — for each runnable agent, call `ensure(base_url, models)`.
   Merge-only: never delete other providers / unrelated keys.
2. **Discover models** — `GET /v1/models`, group by farm prefixes
   (`gcli/`, `alims-intl/`, `qd/`, `mi/`). Embedding-like ids skipped.
3. **Jobs** — one session per `(agent, farm, model)`.
4. **Session** — unique workspace dir + `session_id` so concurrent
   `--continue` / `--last` do not cross-talk.
5. **3 turns** — default prompts check same-session continuity (`P1_OK` → `P3_OK`).
6. **Save outputs** under `.scratch/farm/<run_id>/…`.

### Output tree

```text
.scratch/farm/<run_id>/
  report.json
  <agent>/<farm>/<model>/
    meta.json
    summary.json
    turn_1.cmd.txt
    turn_1.stdout.txt
    turn_1.stderr.txt
    turn_2.…
    turn_3.…
    workspace/          # per-job cwd for session isolation
```

## Runnable agents (wired)

| Agent | Module | Non-interactive pattern |
|-------|--------|-------------------------|
| hermes | `agents/hermes.py` | `hermes chat -q … -Q` |
| pi | `agents/pi.py` | `pi -p --session-id …` |
| aider | `agents/aider.py` | `aider --message …` |
| codex | `agents/codex.py` | `codex exec` + `resume --last` |
| opencode | `agents/opencode.py` | `opencode run -m provider/model` |
| qwen | `agents/qwen.py` | `qwen -p -m …` |
| crush | `agents/crush.py` | `crush run` + per-job `--data-dir` |
| kilo | `agents/kilo.py` | `kilo run` (opencode-family) |
| claude | `agents/claude.py` | backup `settings.json`, swap to 9Router, restore |
| grok | `agents/grok.py` | `grok -p`; `[model.fastapi-9router-*]` |
| vibe | `agents/vibe.py` | `vibe -p`; `VIBE_ACTIVE_MODEL` |
| kimi | `agents/kimi.py` | `kimi -p -m provider/model` |
| cline | `agents/cline.py` | `cline -P openai` + isolated data dir |
| cmd | `agents/commandcode.py` | `cmd -p -m --yolo` |
| copilot | `agents/copilot.py` | `copilot -p` + `COPILOT_PROVIDER_*` |
| kilo | `agents/kilo.py` | `kilo run` (opencode-family) |
| mimo | `agents/mimo.py` | `mimo run` (opencode-family) |
| reasonix | `agents/reasonix.py` | `reasonix -p --model` |

Aliases (same binary, listed as SKIP): `cmdc`, `command-code`,
`commandcode` → cmd; `kilocode` → kilo; `agent`, `cursor` →
cursor-agent.

Cannot farm (vendor auth / catalog): `agy`, `droid`, `kimchi`,
`kiro-cli`, `kiro-cli-chat`, `cursor-agent`, `qodercli`, `zero`.
Not chat CLIs: `kiro-cli-term`, `vibe-acp`, `vibe-app-server`.

Workspace paths passed to `--in` / `-C` / `--cwd` are **absolute**.
The runner also `chdir`s into that workspace, so relative paths
must never be used (they resolve inside the workspace and fail).

## Add a new agent

1. Create `scripts/agent_farm/agents/<name>.py`:

```python
from pathlib import Path
from typing import Any

from ._base import AgentPlugin


class FooAgent(AgentPlugin):
    name = "foo"
    binary = "foo"
    supports_custom_openai = True
    notes = "foo -p …"

    def ensure(self, base_url: str, models: list[str]) -> dict[str, Any]:
        # Merge provider pointing at base_url; do not wipe other config.
        return {"ok": True, "changed": False}

    def build_cmds(
        self,
        model: str,
        prompts: list[str],
        work_dir: Path,
        api_key: str,
        session_id: str,
    ) -> list[list[str]]:
        # One argv list per prompt; keep the same session across turns.
        return [["foo", "-p", "-m", model, p] for p in prompts]
```

2. Register in `agents/__init__.py`:

```python
from .foo import FooAgent

_IMPLEMENTED.append(FooAgent())  # or add inline in the list
```

3. Verify:

```bash
python3 scripts/agent_farm_chat_test.py --list
python3 scripts/agent_farm_chat_test.py --dry-run --skip-ensure \
  --agents foo --models 'mi/mistral-small-latest'
```

### Rules for `ensure`

- Check if the custom provider already exists → update gaps only.
- Never delete other providers, keys, or unrelated settings.
- Prefer append / field fill. Avoid rewriting whole YAML when comments matter
  (see Hermes).

### Rules for `build_cmds`

- Return `len(prompts)` command lists (default 3).
- Use `work_dir` / `session_id` for isolation under `--max-workers > 1`.
- Do not hard-code process timeouts in the plugin; let the runner’s
  optional `--timeout` handle kills.

## Timeout policy

Default is **180 seconds per turn**. A hung CLI (Copilot auth, Cline TTY,
Kiro OAuth) is killed instead of blocking the farm for hours.

Use `--timeout 0` only when you intentionally want no kill.

## Safety

- Do not commit API keys or `.scratch/` artifacts.
- `ensure` may write under `~/.hermes`, `~/.pi`, `~/.codex`, etc.
  Prefer `--dry-run` / `--ensure-only` when validating changes.
- Farm runs can generate many upstream requests; start with
  `--agents` + `--models` subsets.
