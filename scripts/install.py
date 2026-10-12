"""Per-user installation; runs with Python 3.9+, runtime requires Python 3.12+."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def default_root():
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "Programs" / "GarminConnectMCP"
    base = Path(os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share"))
    if not base.is_absolute():
        raise ValueError("XDG_DATA_HOME must be an absolute path")
    return base / "garmin-connect-mcp/application"


def write_atomic(path, content):
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def install(source, root, python=None, uv=None, remote=False):
    source, root = source.resolve(), root.expanduser().absolute()
    if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
        raise ValueError("Install directory cannot be a link")
    version = (source / "VERSION").read_text(encoding="utf-8").strip()
    # Environments contain absolute paths: build at the final location, then
    # publish the launcher only after installation and smoke checks succeed.
    release = root / "releases" / (version + "-" + uuid.uuid4().hex[:8])
    release.mkdir(parents=True)
    if os.name != "nt":
        root.chmod(0o700)
    environment = release / "environment"
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(root / "cache")
    env["UV_PYTHON_INSTALL_DIR"] = str(root / "python")
    env["PIP_CACHE_DIR"] = str(root / "cache/pip")
    env["UV_SYSTEM_CERTS"] = "true"
    env["UV_PYTHON_PREFERENCE"] = "only-managed"
    if uv:
        subprocess.run([uv, "venv", "--python", python or "3.13", str(environment)], check=True, env=env)
    else:
        executable = python or sys.executable
        subprocess.run([executable, "-c", "import sys; assert sys.version_info >= (3,12), 'Python 3.12+ or uv required'"], check=True)
        subprocess.run([executable, "-m", "venv", str(environment)], check=True)
    runtime = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requirement = str(source) + ("[remote]" if remote else "")
    command = ([uv, "pip", "install", "--python", str(runtime)] if uv else [str(runtime), "-m", "pip", "install"])
    subprocess.run(command + [requirement], check=True, env=env)
    subprocess.run([str(runtime), "-c",
        "import asyncio; from garmin_connect_mcp.server import create_server; "
        "import tempfile; from pathlib import Path; "
        "from garmin_connect_mcp.auth import TokenStore; from garmin_connect_mcp.service import GarminService; "
        "directory = tempfile.TemporaryDirectory(); "
        "assert len(asyncio.run(create_server(GarminService(TokenStore(Path(directory.name)))).list_tools())) == 44; "
        "directory.cleanup()"], check=True)
    marketplace = release / "marketplace"
    shutil.copytree(source / "plugins", marketplace / "plugins")
    shutil.copytree(source / ".agents/plugins", marketplace / ".agents/plugins")
    manifest_path = marketplace / "plugins/garmin-connect/.mcp.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["mcpServers"]["garmin-connect"]["command"] = str(runtime)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    metadata = {"version": version, "python": str(runtime), "marketplace": str(marketplace), "remote": remote}
    bin_dir = root / "bin"
    bin_dir.mkdir(exist_ok=True)
    if os.name == "nt":
        # PowerShell is the supported launcher, including paths with spaces.
        quoted = str(runtime).replace("'", "''")
        launcher = bin_dir / "garmin-connect.ps1"
        write_atomic(launcher, "& '" + quoted + "' -m garmin_connect_mcp.manage @args\nexit $LASTEXITCODE\n")
    else:
        import shlex
        launcher = bin_dir / "garmin-connect"
        write_atomic(launcher, "#!/bin/sh\nexec " + shlex.quote(str(runtime)) + " -m garmin_connect_mcp.manage \"$@\"\n")
        launcher.chmod(0o700)
    metadata["launcher"] = str(launcher)
    write_atomic(root / "installation.json", json.dumps(metadata, indent=2) + "\n")
    (release / "installation.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print("Installed " + version + ". Launcher: " + str(launcher))
    print("Next: run the launcher with login, then verify. No environment activation or cd needed.")
    return launcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, default=default_root())
    parser.add_argument("--python")
    parser.add_argument("--uv")
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()
    install(Path(__file__).resolve().parent.parent, args.install_dir, args.python, args.uv, args.remote)


if __name__ == "__main__":
    main()
