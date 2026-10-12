"""User-only login command, separate from MCP tools."""

import argparse
import sys

from .auth import TokenStore, interactive_login, restore_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Garmin Connect MCP with default-enabled reviewed writes")
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
            print("Login verified; session saved locally with " +
                  ("Windows account encryption." if sys.platform == "win32" else "owner-only file permissions."))
        elif args.command == "verify":
            from .runtime import session_lock
            with session_lock(store):
                client = restore_session(store)
                client.get_activities(0, 1)
                store.save(client.client.dumps())
            print("Saved session verified with Garmin.")
        else:
            from .runtime import session_lock
            with session_lock(store):
                store.clear()
            print("Local session removed. This does not revoke Garmin's issued token.")
    except Exception:
        print("Garmin connection failed. Check login/MFA, network access, and the local session; no secrets were logged.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

