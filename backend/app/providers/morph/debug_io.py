"""Write Morph upstream response body to .scratch (full, no truncate)."""

from __future__ import annotations

from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[4] / ".scratch"
_RES = _SCRATCH / "morph-provider-response-latest.txt"


def save_provider_response(raw: str) -> None:
    try:
        _SCRATCH.mkdir(parents=True, exist_ok=True)
        _RES.write_text(raw, encoding="utf-8")
    except Exception:
        pass
