"""On-disk paths for MITM CA, PID, and dumps."""

from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    # backend/app/services/mitm/paths.py → repo root
    return Path(__file__).resolve().parents[4]


def _data_dir() -> Path:
    configured = os.environ.get("DATA_DIR")
    if configured:
        path = Path(configured)
        path.mkdir(parents=True, exist_ok=True)
        return path
    path = _repo_root() / ".scratch"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = _data_dir()
MITM_DIR = Path(os.environ.get("MITM_DIR", DATA_DIR / "mitm"))
MITM_DIR.mkdir(parents=True, exist_ok=True)

PID_FILE = MITM_DIR / ".mitm.pid"
CA_CERT = MITM_DIR / "rootCA.crt"
CA_KEY = MITM_DIR / "rootCA.key"
DEFAULT_ROUTER_BASE = "http://127.0.0.1:8013"


def cert_paths() -> tuple[Path, Path]:
    return CA_CERT, CA_KEY


def cert_files_exist() -> bool:
    return CA_CERT.is_file() and CA_KEY.is_file()
