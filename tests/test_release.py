"""Public release metadata stays consistent and portable."""
import os
import tomllib
from pathlib import Path
from types import SimpleNamespace


def test_release_metadata():
    root = Path(__file__).resolve().parents[1]
    assert (root / "VERSION").read_text().strip() == tomllib.loads(
        (root / "pyproject.toml").read_text())["project"]["version"]
    for name in ("README.md", "CHANGELOG", "LICENSE", "CONTRIBUTING", "NOTICE"):
        assert (root / name).read_text(encoding="utf-8").strip()


def test_windows_storage_without_legacy_drive(monkeypatch, tmp_path):
    from garmin_connect_mcp import auth
    monkeypatch.delenv("GARMIN_MCP_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(auth, "os", SimpleNamespace(name="nt", environ=os.environ))
    monkeypatch.setattr(Path, "is_dir", lambda self: False)
    assert str(auth.data_directory()).endswith("garmin-connect-mcp")
