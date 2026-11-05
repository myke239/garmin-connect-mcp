"""Supervisor-facing monitor; JSON heartbeats, nonzero once-mode failures, no health data."""
import argparse
import json
import time

from .auth import data_directory
from .review_state import ReviewStore, monitor
from .runtime import session_lock


def check(store):
    try:
        with session_lock(store.store):
            state = store._load()
        result = monitor(state, store.clock())
        if not state["schedules"]:
            result.update(healthy=False, alerts=[{"code": "NO_REVIEW_SCHEDULES", "message": "No host schedules are registered."}])
        # Monitoring channels contain occurrence IDs/status, never profile/food/report content.
        result["alert_count"] = len(result["alerts"])
        result["alerts"] = result["alerts"][:100]
        result["alerts_truncated"] = result["alert_count"] > 100
        return result, 0 if result["healthy"] else 1
    except Exception:  # noqa: BLE001 - report every monitor failure without leaking private storage details
        return {"healthy": False, "alerts": [{"code": "REVIEW_MONITOR_FAILED",
                "message": "Could not inspect review state; check storage access, encryption and configuration."}],
                "notification_sent": False}, 2


def main():
    parser = argparse.ArgumentParser(description="Emit review health JSON for an independent alerting supervisor. Does not send notifications.")
    parser.add_argument("--once", action="store_true", help="Exit 0 healthy, 1 review alert, 2 monitor/storage failure")
    parser.add_argument("--interval", type=int, default=60, help="Heartbeat interval in seconds (10-3600)")
    args = parser.parse_args()
    if not 10 <= args.interval <= 3600:
        parser.error("interval must be 10-3600 seconds")
    store = ReviewStore(data_directory())
    while True:
        result, code = check(store)
        print(json.dumps(result), flush=True)
        if args.once:
            raise SystemExit(code)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
