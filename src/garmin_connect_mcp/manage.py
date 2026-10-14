"""Directory-independent launch commands for installed users."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from . import __version__
from .auth import TokenStore, data_directory


def installation():
    # Installed runtime: <release>/environment/{bin,Scripts}/python.
    path = (Path(sys.executable).absolute().parent if getattr(sys,"frozen",False) else Path(sys.executable).absolute().parents[2]) / "installation.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None



def register_plugin(codex, marketplace):
    """Replace only our known one-plugin marketplace; restore it on failure."""
    result = subprocess.run([codex, "plugin", "marketplace", "list", "--json"],
                            check=True, capture_output=True, text=True)
    entries = json.loads(result.stdout)["marketplaces"]
    previous = next((entry["root"] for entry in entries if entry["name"] == "myke-garmin"), None)
    changed = previous is not None and Path(previous).resolve() != Path(marketplace).resolve()
    if changed:
        catalog = Path(previous) / ".agents/plugins/marketplace.json"
        document = json.loads(catalog.read_text(encoding="utf-8"))
        if document.get("name") != "myke-garmin" or [item["name"] for item in document["plugins"]] != ["garmin-connect"]:
            raise ValueError("Existing Garmin marketplace has unexpected plugins; inspect it before replacing.")
        subprocess.run([codex, "plugin", "marketplace", "remove", "myke-garmin"], check=True)
    added = False
    try:
        subprocess.run([codex, "plugin", "marketplace", "add", marketplace], check=True)
        added = True
        subprocess.run([codex, "plugin", "add", "garmin-connect@myke-garmin"], check=True)
    except subprocess.CalledProcessError:
        if changed:
            if added:
                subprocess.run([codex, "plugin", "marketplace", "remove", "myke-garmin"], check=True)
            subprocess.run([codex, "plugin", "marketplace", "add", previous], check=True)
            subprocess.run([codex, "plugin", "add", "garmin-connect@myke-garmin"], check=True)
        raise

def main() -> None:
    parser = argparse.ArgumentParser(description="Garmin Connect setup and launch commands")
    parser.add_argument("command", choices=["login", "verify", "logout", "serve", "approve",
        "tunnel-setup", "tunnel", "tunnel-status", "doctor", "install-plugin",
        "writes-enable", "writes-disable", "writes-status", "archive-enable", "archive-disable", "archive-status", "secure-storage-status", "secure-storage-migrate", "catalog-check", "install-local", "installer-register", "installer-unregister", "fit-setup", "desktop", "diagnostics", "background-start", "background-stop", "background-status", "background-install", "background-uninstall"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "serve":
        if args.arguments:parser.error("serve takes no arguments")
        from .server import main as serve
        serve();return
    if args.command == "doctor":
        if args.arguments:
            parser.error("doctor takes no arguments")
        metadata = installation()
        print(json.dumps({"version": __version__, "python": sys.version.split()[0],
            "installed": metadata is not None, "remote_available": remote_available(),
            "session_saved": TokenStore().exists(), "data_directory": str(data_directory())}, indent=2))
        return
    if args.command == "install-plugin":
        if args.arguments:
            parser.error("install-plugin takes no arguments")
        metadata = installation()
        codex = shutil.which("codex")
        if not metadata or not codex:
            parser.error("An installed runtime and the Codex CLI on PATH are required.")
        register_plugin(codex, metadata["marketplace"])
        print("Plugin installed. Open a new Codex chat.")
        return
    mapping = {"installer-register":("frozen_install",["--register-bundle"]),"installer-unregister":("frozen_install",["--unregister-bundle"]),"fit-setup":("fit_support",[]),"install-local":("frozen_install",[]),"desktop":("desktop",[]),"diagnostics":("diagnostics",[]),**{"background-"+v:("background",[v]) for v in ("start","stop","status","install","uninstall")},"catalog-check":("catalog_drift",["check"]),"secure-storage-status":("protected_storage",["status"]),"secure-storage-migrate":("protected_storage",["migrate"]),"archive-enable":("archive",["enable"]),"archive-disable":("archive",["disable"]),"archive-status":("archive",["status"]), "writes-enable": ("writes", ["enable"]), "writes-disable": ("writes", ["disable"]),
        "writes-status": ("writes", ["status"]), "approve": ("remote", ["approve"]), "tunnel-setup": ("tunnel", ["setup"]),
        "tunnel": ("tunnel", ["run"]), "tunnel-status": ("tunnel", ["status"])}
    module, prefix = mapping.get(args.command, ("cli", [args.command]))
    if module in {"remote", "tunnel"} and not remote_available():
        parser.error("Re-run the installer with --remote (Windows: -Remote) to enable phone access.")
    raise SystemExit(subprocess.call(__import__("garmin_connect_mcp.launching",fromlist=["command"]).command(module,[*prefix,*args.arguments])))


def remote_available() -> bool:
    import importlib.util
    return all(importlib.util.find_spec(name) is not None for name in ("ngrok", "uvicorn"))


if __name__ == "__main__":
    main()
