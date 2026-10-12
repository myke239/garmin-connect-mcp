"""Offline installation contract tests; no package/network/account access."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

from garmin_connect_mcp import manage

spec = importlib.util.spec_from_file_location("installer", Path(__file__).parents[1] / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def source_tree(root):
    root.mkdir()
    (root / "VERSION").write_text("9.9.9")
    plugin = root / "plugins/garmin-connect"
    plugin.mkdir(parents=True)
    (plugin / ".mcp.json").write_text(json.dumps({"mcpServers": {"garmin-connect": {"command": "original"}}}))
    catalog = root / ".agents/plugins"
    catalog.mkdir(parents=True)
    (catalog / "marketplace.json").write_text("{}")
    return root


def test_install_publishes_isolated_plugin_without_editing_source(tmp_path, monkeypatch):
    source = source_tree(tmp_path / "source")
    root = tmp_path / "install with spaces"
    calls = []
    monkeypatch.setattr(installer.subprocess, "run", lambda args, **kwargs: calls.append(args))
    launcher = installer.install(source, root, python="runtime-python", remote=True)
    metadata = json.loads((root / "installation.json").read_text())
    assert metadata["remote"] is True
    assert "install with spaces" in metadata["python"]
    manifest = Path(metadata["marketplace"]) / "plugins/garmin-connect/.mcp.json"
    assert json.loads(manifest.read_text())["mcpServers"]["garmin-connect"]["command"] == metadata["python"]
    assert json.loads((source / "plugins/garmin-connect/.mcp.json").read_text())["mcpServers"]["garmin-connect"]["command"] == "original"
    assert any(str(source.resolve()) + "[remote]" in call for call in calls)
    assert "-m garmin_connect_mcp.manage" in launcher.read_text()
    assert "activate" not in launcher.read_text().lower()


def test_failed_update_preserves_working_launcher_and_receipt(tmp_path, monkeypatch):
    source = source_tree(tmp_path / "source")
    root = tmp_path / "installed"
    (root / "bin").mkdir(parents=True)
    name = "garmin-connect.ps1" if os.name == "nt" else "garmin-connect"
    launcher = root / "bin" / name
    launcher.write_text("working")
    receipt = root / "installation.json"
    receipt.write_text('{"version":"old"}')
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])
    monkeypatch.setattr(installer.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        installer.install(source, root)
    assert launcher.read_text() == "working"
    assert json.loads(receipt.read_text())["version"] == "old"


def test_uv_install_keeps_managed_python_and_cache_in_install_root(tmp_path, monkeypatch):
    source = source_tree(tmp_path / "source")
    root = tmp_path / "installed"
    calls = []
    monkeypatch.setattr(installer.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    installer.install(source, root, uv="/tools/uv")
    assert calls[0][0][:4] == ["/tools/uv", "venv", "--python", "3.13"]
    assert calls[0][1]["env"]["UV_PYTHON_INSTALL_DIR"] == str(root / "python")
    assert calls[1][0][:3] == ["/tools/uv", "pip", "install"]


def test_management_approve_uses_same_interpreter(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(manage, "remote_available", lambda: True)
    monkeypatch.setattr(manage.sys, "argv", ["manage", "approve", "synthetic-ticket"])
    monkeypatch.setattr(manage.subprocess, "call", lambda args: calls.append(args) or 0)
    with pytest.raises(SystemExit) as error:
        manage.main()
    assert error.value.code == 0
    assert calls == [[manage.sys.executable, "-m", "garmin_connect_mcp.remote", "approve", "synthetic-ticket"]]


def test_management_rejects_remote_without_extras(monkeypatch):
    monkeypatch.setattr(manage, "remote_available", lambda: False)
    monkeypatch.setattr(manage.sys, "argv", ["manage", "tunnel"])
    with pytest.raises(SystemExit) as error:
        manage.main()
    assert error.value.code == 2


def test_linux_launcher_handles_apostrophes_and_arguments(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX launcher execution")
    source = source_tree(tmp_path / "source")
    root = tmp_path / "someone's install"
    monkeypatch.setattr(installer.subprocess, "run", lambda *args, **kwargs: None)
    launcher = installer.install(source, root)
    monkeypatch.undo()
    runtime = Path(json.loads((root / "installation.json").read_text())["python"])
    runtime.parent.mkdir(parents=True)
    runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    runtime.chmod(0o700)
    output = subprocess.check_output([str(launcher), "approve", "ticket with spaces"], text=True, cwd="/")
    assert output.splitlines() == ["-m", "garmin_connect_mcp.manage", "approve", "ticket with spaces"]


def test_linux_data_directory_honors_xdg(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("Linux XDG storage")
    from garmin_connect_mcp.auth import data_directory
    monkeypatch.delenv("GARMIN_MCP_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert data_directory() == tmp_path / "data/garmin-connect-mcp"
    monkeypatch.setenv("XDG_DATA_HOME", "relative")
    with pytest.raises(ValueError):
        data_directory()


def test_approval_preserves_venv_path(monkeypatch, tmp_path):
    from garmin_connect_mcp import remote
    monkeypatch.setattr(manage, "installation", lambda: None)
    executable = tmp_path / "venv/bin/python"
    monkeypatch.setattr(remote.sys, "executable", str(executable))
    command = remote.approval_command("test-ticket")
    assert "venv" in command
    assert "approve" in command


def test_installed_approval_uses_launcher(monkeypatch, tmp_path):
    from garmin_connect_mcp import remote
    launcher = tmp_path / "garmin-connect"
    launcher.touch()
    monkeypatch.setattr(manage, "installation", lambda: {"launcher": str(launcher)})
    command = remote.approval_command("test-ticket")
    assert str(launcher) in command
    assert "garmin_connect_mcp.remote" not in command



def marketplace_tree(root, names):
    catalog = root / ".agents/plugins"
    catalog.mkdir(parents=True)
    (catalog / "marketplace.json").write_text(json.dumps({"name": "myke-garmin",
        "plugins": [{"name": name} for name in names]}))
    return str(root)


def test_plugin_registration_migrates_only_garmin_marketplace(tmp_path, monkeypatch):
    previous = marketplace_tree(tmp_path / "old", ["garmin-connect"])
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"marketplaces": [
            {"name": "other", "root": "/do-not-touch"}, {"name": "myke-garmin", "root": previous}]}))
    monkeypatch.setattr(manage.subprocess, "run", run)
    manage.register_plugin("codex", str(tmp_path / "new"))
    assert calls[1] == ["codex", "plugin", "marketplace", "remove", "myke-garmin"]
    assert len(calls) == 4
    assert all("/do-not-touch" not in call for call in calls)


def test_plugin_registration_restores_previous_source_on_failure(tmp_path, monkeypatch):
    previous = marketplace_tree(tmp_path / "old", ["garmin-connect"])
    new = str(tmp_path / "new")
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        if args == ["codex", "plugin", "marketplace", "add", new]:
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"marketplaces": [
            {"name": "myke-garmin", "root": previous}]}))
    monkeypatch.setattr(manage.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        manage.register_plugin("codex", new)
    assert calls[-2] == ["codex", "plugin", "marketplace", "add", previous]
    assert calls[-1] == ["codex", "plugin", "add", "garmin-connect@myke-garmin"]


def test_plugin_registration_refuses_to_remove_unexpected_plugins(tmp_path, monkeypatch):
    previous = marketplace_tree(tmp_path / "old", ["garmin-connect", "someone-elses-plugin"])
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"marketplaces": [
            {"name": "myke-garmin", "root": previous}]}))
    monkeypatch.setattr(manage.subprocess, "run", run)
    with pytest.raises(ValueError):
        manage.register_plugin("codex", str(tmp_path / "new"))
    assert len(calls) == 1
