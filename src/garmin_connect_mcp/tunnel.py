"""Run the personal OAuth service through the official ngrok SDK."""

import argparse
import getpass
import json
import os
import socket
import sys

from .auth import TokenStore, data_directory
from .remote import create_deployment_app
from .endpoints import CANONICAL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "run", "status"])
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    store = TokenStore(data_directory() / "remote-tunnel")
    status = TokenStore(data_directory() / "remote-status")
    if args.command == "setup":
        if not sys.stdin.isatty():
            raise SystemExit("Run setup in your own terminal so the token stays private.")
        token = getpass.getpass("Paste your ngrok authtoken (hidden): ").strip()
        if not token or any(character.isspace() for character in token):
            raise SystemExit("Expected a single ngrok authtoken")
        store.save(json.dumps({"authtoken": token}))
        print("Tunnel token saved with " +
              ("Windows account encryption." if os.name == "nt" else "owner-only file permissions."))
        return
    if args.command == "status":
        print(status.load() if status.exists() else "Tunnel has not started.")
        return
    if not store.exists():
        raise SystemExit("Run python -m garmin_connect_mcp.tunnel setup first.")
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Use an unprivileged local port")
    import ngrok
    import uvicorn
    # Reserve the port before forwarding; never expose another local process.
    listener_socket = socket.socket()
    try:
        listener_socket.bind(("127.0.0.1", args.port))
    except OSError as error:
        listener_socket.close()
        raise SystemExit(f"Port {args.port} is already in use or unavailable. If your shared MCP gateway is running, use its existing HTTPS origin; do not start a second tunnel. Run diagnostics to check the service.") from error
    listener_socket.listen(128)
    listener = None
    try:
        listener = ngrok.forward(f"http://127.0.0.1:{args.port}",
            authtoken=json.loads(store.load())["authtoken"])
        origin = listener.url()
        app, provider = create_deployment_app(origin, args.port)
        with provider.state():
            pass
        status.save(json.dumps({"url": origin + CANONICAL.mcp_path, "pid": os.getpid(), "port": args.port}))
        print("Authenticated Garmin MCP: " + origin + CANONICAL.mcp_path, flush=True)
        config = uvicorn.Config(app, log_level="warning", access_log=False,
            proxy_headers=False, timeout_keep_alive=5, limit_concurrency=16)
        uvicorn.Server(config).run(sockets=[listener_socket])
    finally:
        if listener is not None:
            ngrok.disconnect(listener.url())
        listener_socket.close()
        status.clear()


if __name__ == "__main__":
    main()
