"""MITM cert generation and host mapping."""

from pathlib import Path

import pytest

from app.services.mitm.cert import generate_root_ca
from app.services.mitm.hosts import get_tool_for_host
from app.services.mitm.process import get_runtime_status


def test_get_tool_for_host() -> None:
    assert get_tool_for_host(
        "api.individual.githubcopilot.com",
    ) == "copilot"
    assert get_tool_for_host(
        "cloudcode-pa.googleapis.com:443",
    ) == "antigravity"
    assert get_tool_for_host("example.com") is None


def test_generate_root_ca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.mitm.cert as cert_mod
    import app.services.mitm.paths as paths_mod

    monkeypatch.setattr(paths_mod, "MITM_DIR", tmp_path)
    monkeypatch.setattr(paths_mod, "CA_CERT", tmp_path / "rootCA.crt")
    monkeypatch.setattr(paths_mod, "CA_KEY", tmp_path / "rootCA.key")
    monkeypatch.setattr(cert_mod, "CA_CERT", tmp_path / "rootCA.crt")
    monkeypatch.setattr(cert_mod, "CA_KEY", tmp_path / "rootCA.key")

    path = generate_root_ca(force=True)
    assert path.is_file()
    assert (tmp_path / "rootCA.key").is_file()
    pem = path.read_text(encoding="utf-8")
    assert "BEGIN CERTIFICATE" in pem


def test_runtime_status_not_running() -> None:
    status = get_runtime_status(port=59999)
    assert status["running"] is False
    assert status["pid"] is None
