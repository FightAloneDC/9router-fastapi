"""Start / stop / status of the MITM child process."""

from __future__ import annotations

import os
import signal
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from app.services.mitm.cert import generate_root_ca
from app.services.mitm.hosts import check_all_dns_status
from app.services.mitm.paths import (
    CA_CERT,
    MITM_DIR,
    PID_FILE,
    cert_files_exist,
)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_pid() -> int | None:
    if not PID_FILE.is_file():
        return None
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if pid <= 0 or not _pid_alive(pid):
        try:
            PID_FILE.unlink()
        except OSError:
            pass
        return None
    return pid


def _health_ok(port: int) -> bool:
    ctx = ssl._create_unverified_context()
    url = f"https://127.0.0.1:{port}/_mitm_health"
    try:
        with urlopen(url, context=ctx, timeout=1.5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return '"ok": true' in body.replace(" ", "") or '"ok":true' in body
    except (URLError, TimeoutError, OSError):
        return False


def get_runtime_status(port: int = 443) -> dict[str, Any]:
    pid = _read_pid()
    running = bool(pid) and _health_ok(port)
    return {
        "running": running,
        "pid": pid if running else None,
        "certExists": cert_files_exist(),
        "certPath": str(CA_CERT) if cert_files_exist() else None,
        "listenPort": port,
        "dnsStatus": check_all_dns_status(),
    }


def start_mitm_process(
    *,
    port: int,
    router_base_url: str,
    ingest_url: str,
    ingest_token: str,
) -> dict[str, Any]:
    """Spawn the HTTPS MITM child. Raises RuntimeError on failure."""
    generate_root_ca(force=False)
    existing = _read_pid()
    if existing and _health_ok(port):
        return get_runtime_status(port)

    if existing:
        try:
            os.kill(existing, signal.SIGTERM)
        except OSError:
            pass
        time.sleep(0.3)

    backend_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["MITM_DIR"] = str(MITM_DIR)
    env["MITM_PORT"] = str(port)
    env["MITM_ROUTER_BASE"] = router_base_url.rstrip("/")
    env["MITM_INGEST_URL"] = ingest_url
    env["MITM_INGEST_TOKEN"] = ingest_token
    env["PYTHONPATH"] = str(backend_root) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    log_path = MITM_DIR / "server.log"
    log_file = open(log_path, "ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.services.mitm.server"],
        cwd=str(backend_root),
        env=env,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    deadline = time.time() + 8
    last_err = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            last_err = ""
            try:
                last_err = (
                    log_path.read_bytes()[-400:]
                    .decode("utf-8", errors="replace")
                )
            except OSError:
                pass
            try:
                PID_FILE.unlink()
            except OSError:
                pass
            raise RuntimeError(
                last_err or f"MITM exited (code {proc.returncode})"
            )
        if _health_ok(port):
            return get_runtime_status(port)
        time.sleep(0.25)

    try:
        proc.kill()
    except OSError:
        pass
    try:
        PID_FILE.unlink()
    except OSError:
        pass
    raise RuntimeError(
        last_err
        or f"MITM did not become healthy on :{port} "
        "(need bind permission for that port)."
    )


def stop_mitm_process() -> None:
    pid = _read_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        time.sleep(0.4)
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    try:
        PID_FILE.unlink()
    except OSError:
        pass
