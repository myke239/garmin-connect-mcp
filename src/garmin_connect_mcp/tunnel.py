"""Run the personal OAuth service through the official ngrok SDK."""

import argparse
import getpass
import json
import os
import socket
import sys

from .auth import TokenStore, data_directory
from .remote import create_http_app


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
        print("Tunnel token saved with Windows account encryption.")
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
    listener_socket.bind(("127.0.0.1", args.port))
    listener_socket.listen(128)
    listener = None
    try:
        listener = ngrok.forward(f"http://127.0.0.1:{args.port}",
            authtoken=json.loads(store.load())["authtoken"])
        origin = listener.url()
        app, provider = create_http_app(origin, args.port)
        with provider.state():
            pass
        status.save(json.dumps({"url": origin + "/mcp", "pid": os.getpid(), "port": args.port}))
        print("Authenticated Garmin MCP: " + origin + "/mcp", flush=True)
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
