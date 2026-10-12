"""User-only login command, separate from MCP tools."""

import argparse
import sys

from .auth import TokenStore, interactive_login, restore_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Garmin Connect MCP")
    parser.add_argument("command", nargs="?", choices=["serve", "login", "verify", "logout"], default="serve")
    args = parser.parse_args()
    if args.command == "serve":
        from .server import main as serve
        serve()
        return
    store = TokenStore()
    try:
        if args.command == "login":
            interactive_login(store)
            print("Login verified; encrypted session saved locally.")
        elif args.command == "verify":
            client = restore_session(store)
            client.get_activities(0, 1)
            store.save(client.client.dumps())
            print("Saved session verified with Garmin.")
        else:
            store.clear()
            print("Local session removed. This does not revoke Garmin's issued token.")
    except Exception:
        print("Garmin connection failed. Check login/MFA, network access, and the local session; no secrets were logged.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

