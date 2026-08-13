"""Shared constants and helpers for agent farm modules."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
DEFAULT_BASE_URL = "http://localhost:8013/v1"
PROVIDER_ID = "fastapi-9router"
PROVIDER_NAME = "FastAPI 9Router"
KEY_ENV = "HERMES_CUSTOM_LOCALHOST_8013_API_KEY"
HERMES_ENV_FILE = HOME / ".hermes" / ".env"

DEFAULT_PROMPTS = [
    "Reply with exactly one line: P1_OK",
    (
        "What token did I require in the previous message? "
        "Reply with exactly one line: P2_OK <that-token>"
    ),
    (
        "Confirm this is turn 3 of the same session. "
        "Reply with exactly one line: P3_OK session-ok"
    ),
]

FARM_MATCHERS: dict[str, re.Pattern[str]] = {
    "grok-cli": re.compile(r"^gcli/|^grok-", re.I),
    "alibaba-studio": re.compile(r"^alims-intl/", re.I),
    "qoder": re.compile(r"^qd/", re.I),
    "mistral": re.compile(r"^mi/", re.I),
}

EXCLUDE_SUBSTR = ("embedding", "embed", "tts", "whisper", "image")


@dataclass
class JobResult:
    agent: str
    farm: str
    model: str
    ok: bool
    exit_codes: list[int] = field(default_factory=list)
    out_dir: str = ""
    error: str = ""
    elapsed_sec: float = 0.0
    error_class: str = ""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    )


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    atomic_write_text(path, existing + text)


def load_api_key() -> str:
    key = os.environ.get(KEY_ENV, "").strip()
    if key:
        return key
    if HERMES_ENV_FILE.is_file():
        for line in HERMES_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == KEY_ENV:
                return v.strip().strip('"').strip("'")
    for env_name in (
        "FASTAPI_9ROUTER_API_KEY",
        "FASTAPI_9ROUTER_API",
        "OPENAI_API_KEY",
    ):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val
    raise SystemExit(
        f"Missing API key. Export {KEY_ENV} or put it in "
        f"{HERMES_ENV_FILE}"
    )


def fetch_models(base_url: str, api_key: str) -> list[str]:
    import urllib.request

    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    ids = [
        m.get("id", "")
        for m in payload.get("data", [])
        if m.get("id")
    ]
    return sorted(set(ids))


def farm_models(all_ids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {name: [] for name in FARM_MATCHERS}
    for mid in all_ids:
        low = mid.lower()
        if any(x in low for x in EXCLUDE_SUBSTR):
            continue
        for farm, pat in FARM_MATCHERS.items():
            if pat.search(mid):
                out[farm].append(mid)
                break
    for farm in out:
        out[farm] = sorted(set(out[farm]))
    return out


def select_farm_models(
    grouped: dict[str, list[str]],
    want_farms: set[str],
    one_per_farm: bool,
) -> dict[str, list[str]]:
    selected: dict[str, list[str]] = {}
    for farm, ids in grouped.items():
        if farm not in want_farms:
            continue
        chosen = list(ids[:1] if one_per_farm else ids)
        if chosen:
            selected[farm] = chosen
    return selected


def job_dirs(
    out_root: Path,
    agent: str,
    farm: str,
    model: str,
) -> tuple[Path, Path]:
    """Absolute per-job output dir and workspace cwd."""
    safe_model = re.sub(r"[^a-zA-Z0-9._-]+", "_", model)
    out_dir = (out_root / agent / farm / safe_model).resolve()
    return out_dir, out_dir / "workspace"


def strip_v1(base_url: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        return root[:-3]
    return root


def classify_error(text: str, exit_code: int) -> str:
    low = (text or "").lower()
    if (
        "no such file" in low
        or "directory not found" in low
        or "chdir" in low
    ):
        return "path"
    if (
        "429" in low
        or "rate limit" in low
        or "rate_limited" in low
    ):
        return "rate_limit"
    if "timeout" in low or exit_code == -9:
        return "timeout"
    if (
        "500" in low
        or "503" in low
        or "internal server" in low
        or "service unavailable" in low
    ):
        return "upstream"
    if exit_code != 0:
        return "exit"
    return ""


def is_retryable(text: str) -> bool:
    return classify_error(text, 1) == "rate_limit"


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments without touching URLs inside strings."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    escape = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < n and text[i] not in "\n\r":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (
                    text[i] == "*" and text[i + 1] == "/"
                ):
                    i += 1
                i = min(i + 2, n)
                continue
        out.append(c)
        i += 1
    return "".join(out)


def load_json_config(path: Path) -> dict[str, Any]:
    """Load JSON or JSONC; prefer strict JSON first."""
    raw = path.read_text()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = json.loads(strip_jsonc(raw))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be a JSON object")
    return data


def merge_opencode_provider(
    config_path: Path,
    base_url: str,
    models: list[str],
) -> dict[str, Any]:
    """Shared merge for opencode-family JSON/JSONC configs."""
    if config_path.is_file():
        data = load_json_config(config_path)
    else:
        data = {}
    providers = data.setdefault("provider", {})
    block = providers.get(PROVIDER_ID)
    changed = False
    model_map = {m: {"name": m} for m in models}
    if block is None:
        providers[PROVIDER_ID] = {
            "npm": "@ai-sdk/openai-compatible",
            "name": PROVIDER_NAME,
            "options": {
                "baseURL": base_url,
                "apiKey": f"{{{KEY_ENV}}}",
            },
            "models": model_map,
        }
        key = os.environ.get(KEY_ENV, "")
        if key:
            providers[PROVIDER_ID]["options"]["apiKey"] = key
        changed = True
    else:
        opts = block.setdefault("options", {})
        if opts.get("baseURL") != base_url:
            opts["baseURL"] = base_url
            changed = True
        existing = block.setdefault("models", {})
        for mid, meta in model_map.items():
            if mid not in existing:
                existing[mid] = meta
                changed = True
    if changed:
        atomic_write_json(config_path, data)
    return {"ok": True, "path": str(config_path), "changed": changed}
