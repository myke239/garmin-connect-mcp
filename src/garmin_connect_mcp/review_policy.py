"""Local owner controls for private review-state mutations, separate from account operations."""
import argparse
import json

from .auth import data_directory
from .review_state import OPERATIONS, ReviewStore
from .runtime import session_lock


def main():
    parser = argparse.ArgumentParser(description="Manage private review-state policy; does not alter Garmin permissions or host tasks")
    parser.add_argument("command", choices=["status", "enable", "disable"])
    parser.add_argument("--operations", nargs="*", choices=sorted(OPERATIONS))
    args = parser.parse_args()
    if args.command == "status" and args.operations is not None:
        parser.error("status cannot change operations")
    store = ReviewStore(data_directory())
    try:
        with session_lock(store.settings):
            policy = json.loads(store.settings.load()) if store.settings.exists() else {"enabled": True}
            if args.command != "status":
                policy["enabled"] = args.command == "enable"
                if args.operations is not None:
                    policy["operations"] = args.operations
                store.settings.save(json.dumps(policy))
        print(json.dumps({"review_policy": policy, "global_writes_disable_still_applies": True,
                          "host_tasks_changed": False}))
    except Exception:  # noqa: BLE001 - command boundary reports a safe error and nonzero exit
        print(json.dumps({"error": "REVIEW_POLICY_ERROR", "message": "Could not access private review policy."}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
