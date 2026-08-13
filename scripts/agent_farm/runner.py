"""CLI runner: ensure providers, farm models, concurrent sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .agents import list_agents, runnable_agents
from .agents._base import AgentPlugin
from .common import (
    DEFAULT_BASE_URL,
    DEFAULT_PROMPTS,
    KEY_ENV,
    JobResult,
    atomic_write_json,
    classify_error,
    farm_models,
    fetch_models,
    is_retryable,
    job_dirs,
    load_api_key,
    select_farm_models,
    utc_stamp,
)


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_SAVED_TERMIOS: object | None = None


def decode_pipe(value: object) -> str:
    """Normalize subprocess output to str (TimeoutExpired may be bytes)."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def timeout_outputs(
    exc: subprocess.TimeoutExpired,
    timeout: float | None,
) -> tuple[str, str]:
    """Decode TimeoutExpired pipes without mixing str and bytes."""
    stdout = decode_pipe(exc.stdout)
    stderr = decode_pipe(exc.stderr)
    stderr += f"\nTIMEOUT after {timeout}s\n"
    return stdout, stderr


def sanitize_status_line(text: str) -> str:
    """Drop CR/ANSI so a child TTY leak cannot rewind the prompt."""
    cleaned = _ANSI_RE.sub("", text)
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    return " ".join(cleaned.split())


def save_tty() -> None:
    """Remember cooked termios so cmd cannot leave raw/no-ONLCR mode."""
    global _SAVED_TERMIOS
    try:
        import termios
        fd = sys.stdout.fileno()
        if os.isatty(fd):
            _SAVED_TERMIOS = termios.tcgetattr(fd)
    except Exception:
        _SAVED_TERMIOS = None


def restore_tty() -> None:
    """Undo raw mode / hidden cursor a child may have set on /dev/tty."""
    try:
        fd = sys.stdout.fileno()
    except Exception:
        return
    if not os.isatty(fd):
        return
    if _SAVED_TERMIOS is not None:
        try:
            import termios
            termios.tcsetattr(
                fd, termios.TCSADRAIN, _SAVED_TERMIOS,
            )
        except Exception:
            pass
    try:
        sys.stdout.write("\033[0m\r\033[?25h")
        sys.stdout.flush()
    except Exception:
        pass


def print_status(line: str) -> None:
    """Print one farm line at column 0 after restoring the TTY."""
    restore_tty()
    print(sanitize_status_line(line), flush=True)


def run_cmd(
    cmd: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout: float | None,
    need_pty: bool,
) -> tuple[int, str, str]:
    """Run one turn. ``need_pty`` wraps the child in ``script`` (Linux)."""
    run_argv = cmd
    if need_pty:
        run_argv = [
            "script",
            "-qefc",
            shlex.join(cmd),
            "/dev/null",
        ]
    proc = subprocess.run(
        run_argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        start_new_session=True,
    )
    return (
        proc.returncode,
        decode_pipe(proc.stdout),
        decode_pipe(proc.stderr),
    )


def run_session(
    agent: AgentPlugin,
    farm: str,
    model: str,
    prompts: list[str],
    out_root: Path,
    api_key: str,
    timeout: float | None,
    dry_run: bool,
    base_url: str,
    retries: int,
) -> JobResult:
    out_dir, job_cwd = job_dirs(out_root, agent.name, farm, model)
    out_dir.mkdir(parents=True, exist_ok=True)
    job_cwd.mkdir(parents=True, exist_ok=True)
    session_id = (
        f"farm-{agent.name}-{farm}-{out_dir.name}-{utc_stamp()}"
    )
    started = time.time()
    try:
        cmds = agent.build_cmds(
            model,
            prompts,
            job_cwd,
            api_key,
            session_id,
        )
    except Exception as exc:  # noqa: BLE001
        return JobResult(
            agent.name,
            farm,
            model,
            False,
            error=f"build_cmds: {exc}",
            error_class="build",
            out_dir=str(out_dir),
        )

    meta = {
        "agent": agent.name,
        "farm": farm,
        "model": model,
        "session_id": session_id,
        "job_cwd": str(job_cwd),
        "prompts": prompts,
        "commands": cmds,
        "started_at": utc_stamp(),
    }
    atomic_write_json(out_dir / "meta.json", meta)
    if dry_run:
        return JobResult(
            agent.name,
            farm,
            model,
            True,
            out_dir=str(out_dir),
            elapsed_sec=time.time() - started,
        )

    env = os.environ.copy()
    env[KEY_ENV] = api_key
    env.setdefault("OPENAI_API_KEY", api_key)
    env.setdefault("OPENAI_BASE_URL", base_url)
    env.setdefault("OPENAI_API_BASE", base_url)
    env.update(agent.extra_env(api_key, base_url, model))
    if timeout is not None and timeout <= 0:
        timeout = None

    exit_codes: list[int] = []
    ok = True
    last_blob = ""
    attempts_allowed = 1 + max(0, retries)
    for idx, cmd in enumerate(cmds, start=1):
        stdout_path = out_dir / f"turn_{idx}.stdout.txt"
        stderr_path = out_dir / f"turn_{idx}.stderr.txt"
        cmd_path = out_dir / f"turn_{idx}.cmd.txt"
        redacted = [
            "***" if (api_key and part == api_key) else part
            for part in cmd
        ]
        cmd_path.write_text(" ".join(redacted) + "\n")
        code = -1
        stdout = ""
        stderr = ""
        for attempt in range(attempts_allowed):
            try:
                code, stdout, stderr = run_cmd(
                    cmd,
                    cwd=str(job_cwd),
                    env=env,
                    timeout=timeout,
                    need_pty=agent.needs_pty,
                )
            except subprocess.TimeoutExpired as exc:
                stdout, stderr = timeout_outputs(exc, timeout)
                code = -9
            except Exception as exc:  # noqa: BLE001
                stdout = ""
                stderr = str(exc)
                code = -1
            stdout = decode_pipe(stdout)
            stderr = decode_pipe(stderr)
            blob = stdout + "\n" + stderr
            if code == 0:
                break
            if (
                attempt + 1 < attempts_allowed
                and is_retryable(blob)
            ):
                time.sleep(min(8.0, 2.0 ** attempt))
                continue
            break
        stdout_path.write_text(stdout)
        stderr_path.write_text(stderr)
        exit_codes.append(code)
        last_blob = stdout + "\n" + stderr
        if code != 0:
            ok = False
            break

    err_class = "" if ok else classify_error(
        last_blob,
        exit_codes[-1] if exit_codes else -1,
    )
    summary = {
        "ok": ok,
        "exit_codes": exit_codes,
        "error_class": err_class,
        "elapsed_sec": round(time.time() - started, 3),
        "finished_at": utc_stamp(),
    }
    atomic_write_json(out_dir / "summary.json", summary)
    return JobResult(
        agent.name,
        farm,
        model,
        ok,
        exit_codes=exit_codes,
        out_dir=str(out_dir),
        elapsed_sec=summary["elapsed_sec"],
        error="" if ok else f"exit_codes={exit_codes}",
        error_class=err_class,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Farm-test modular agents against 9Router. "
            "Add agents under scripts/agent_farm/agents/."
        ),
    )
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("tests/agent_farm_runs"),
    )
    p.add_argument("--agents", default="")
    p.add_argument(
        "--farms",
        default="grok-cli,alibaba-studio,qoder,mistral",
    )
    p.add_argument("--models", default="")
    p.add_argument("--max-workers", type=int, default=2)
    p.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="Per-turn kill after SEC (default 180; 0 = none)",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Extra attempts per turn on HTTP 429",
    )
    p.add_argument(
        "--one-per-farm",
        action="store_true",
        help="Use only the first model from each farm",
    )
    p.add_argument(
        "--probe",
        action="store_true",
        help="Smoke test: 1 prompt, 1 model per farm, all agents",
    )
    p.add_argument("--ensure-only", action="store_true")
    p.add_argument("--skip-ensure", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--prompt-file", type=Path, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    save_tty()

    if args.list:
        print("=== All registered agents ===")
        for plugin in list_agents():
            path = plugin.binary_path() or "NOT FOUND"
            flag = "RUN" if plugin.supports_custom_openai else "SKIP"
            reason = (
                f" ({plugin.skip_reason})"
                if plugin.skip_reason
                else ""
            )
            print(
                f"[{flag}] {plugin.name}: {path} "
                f"| {plugin.notes}{reason}"
            )
        return 0

    api_key = load_api_key()
    os.environ[KEY_ENV] = api_key
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = args.base_url
    os.environ["OPENAI_API_BASE"] = args.base_url

    want_agents = {
        a.strip() for a in args.agents.split(",") if a.strip()
    }
    want_farms = {
        a.strip() for a in args.farms.split(",") if a.strip()
    }
    active = runnable_agents(want_agents or None)
    if not active:
        print("No runnable agents", file=sys.stderr)
        return 2

    one_per = args.one_per_farm or args.probe
    if args.models:
        selected = {
            "manual": [
                m.strip()
                for m in args.models.split(",")
                if m.strip()
            ]
        }
        if one_per:
            selected["manual"] = selected["manual"][:1]
    else:
        try:
            all_ids = fetch_models(args.base_url, api_key)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to fetch models: {exc}", file=sys.stderr)
            return 2
        grouped = farm_models(all_ids)
        selected = select_farm_models(
            grouped,
            want_farms,
            one_per_farm=one_per,
        )

    all_model_ids = sorted(
        {m for ids in selected.values() for m in ids}
    )
    print("Farms/models:")
    for farm, ids in selected.items():
        print(f"  {farm}: {len(ids)} -> {ids}")

    def _teardown() -> None:
        for plugin in active:
            try:
                result = plugin.teardown()
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "error": str(exc)}
            if result.get("skipped"):
                continue
            print(f"  teardown {plugin.name}: {result}")

    ensure_failed = 0
    try:
        if not args.skip_ensure:
            print("\nEnsuring custom providers (merge-only)...")
            for plugin in active:
                try:
                    result = plugin.ensure(
                        args.base_url,
                        all_model_ids,
                    )
                except Exception as exc:  # noqa: BLE001
                    result = {"ok": False, "error": str(exc)}
                print(f"  {plugin.name}: {result}")
                if not result.get("ok", False):
                    ensure_failed += 1
        else:
            for plugin in active:
                plugin.prepare(args.base_url, all_model_ids)

        if args.ensure_only:
            print("ensure-only done")
            return 1 if ensure_failed else 0

        prompts = list(DEFAULT_PROMPTS)
        if args.prompt_file:
            prompts = json.loads(args.prompt_file.read_text())
            if not isinstance(prompts, list) or len(prompts) < 1:
                raise SystemExit("--prompt-file must be JSON list")
        if args.probe:
            prompts = prompts[:1]
            print("Probe mode: 1 prompt, 1 model per farm")

        run_id = utc_stamp()
        out_root = (args.out_dir / run_id).resolve()
        out_root.mkdir(parents=True, exist_ok=True)

        jobs: list[tuple[AgentPlugin, str, str]] = []
        for farm, models in selected.items():
            for model in models:
                for plugin in active:
                    jobs.append((plugin, farm, model))

        print(
            f"\nStarting {len(jobs)} sessions "
            f"(workers={args.max_workers}, timeout={args.timeout})"
        )
        results: list[JobResult] = []
        with ThreadPoolExecutor(
            max_workers=max(1, args.max_workers)
        ) as pool:
            futs = {
                pool.submit(
                    run_session,
                    plugin,
                    farm,
                    model,
                    prompts,
                    out_root,
                    api_key,
                    args.timeout,
                    args.dry_run,
                    args.base_url,
                    args.retries,
                ): (plugin.name, farm, model)
                for plugin, farm, model in jobs
            }
            for fut in as_completed(futs):
                name, farm, model = futs[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001
                    res = JobResult(
                        name,
                        farm,
                        model,
                        False,
                        error=str(exc),
                    )
                results.append(res)
                status = "OK" if res.ok else "FAIL"
                klass = (
                    f" {res.error_class}" if res.error_class else ""
                )
                print_status(
                    f"[{status}]{klass} {res.agent} | {res.farm} | "
                    f"{res.model} ({res.elapsed_sec}s) {res.error}"
                )

        by_class: dict[str, int] = {}
        for res in results:
            if res.error_class:
                by_class[res.error_class] = (
                    by_class.get(res.error_class, 0) + 1
                )
        report = {
            "run_id": run_id,
            "base_url": args.base_url,
            "probe": args.probe,
            "agents": [p.name for p in active],
            "farms": selected,
            "ok": sum(1 for r in results if r.ok),
            "fail": sum(1 for r in results if not r.ok),
            "error_classes": by_class,
            "results": [r.__dict__ for r in results],
        }
        report_path = out_root / "report.json"
        atomic_write_json(report_path, report)
        print(f"\nReport: {report_path}")
        print(f"OK={report['ok']} FAIL={report['fail']}")
        return 0 if report["fail"] == 0 else 1
    finally:
        _teardown()
        restore_tty()


if __name__ == "__main__":
    # Allow: python3 scripts/agent_farm/runner.py
    raise SystemExit(main())
