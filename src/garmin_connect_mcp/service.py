"""Read-only application service; no tool accepts an arbitrary endpoint."""

import threading
import time
import copy
from collections import OrderedDict
from datetime import datetime, timezone

from .auth import TokenStore, restore_session
from .data import activity, validate_id, validate_range, splits, heart_rate_samples, strength_sets
from .runtime import bounded_request, RequestError


class GarminService:
    def __init__(self, store=None, runner=bounded_request):
        self.store = store or TokenStore()
        self.runner = runner
        self.lock = threading.RLock()
        self.cache = OrderedDict()
        self.metadata = threading.local()
        self.session_marker = None

    def marker(self):
        try:
            stat = self.store.path.stat()
            return (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            return None

    def session_state(self):
        return "saved_session" if self.store.exists() else "auth_required"

    def call(self, method, *args, **kwargs):
        with self.lock:
            marker = self.marker()
            if marker != self.session_marker:
                self.cache.clear()
                self.session_marker = marker
            key = (method, repr(args), repr(sorted(kwargs.items())))
            now = time.monotonic()
            entry = self.cache.get(key)
            if entry and now - entry[0] < 120:
                self.cache.move_to_end(key)
                self.metadata.value = {"cached": True, "fetched_at_utc": entry[1]}
                return copy.deepcopy(entry[2])
            for attempt in range(2):
                try:
                    result = self.runner(self.store.directory, method, args, kwargs)
                    break
                except RequestError as error:
                    if attempt or error.code not in {"NETWORK_ERROR", "UPSTREAM_ERROR"}:
                        if error.code == "AUTH_REQUIRED":
                            self.cache.clear()
                        raise
                    time.sleep(.5)
            fetched = datetime.now(timezone.utc).isoformat()
            self.cache[key] = (time.monotonic(), fetched, copy.deepcopy(result))
            self.session_marker = self.marker()
            while len(self.cache) > 128:
                self.cache.popitem(last=False)
            self.metadata.value = {"cached": False, "fetched_at_utc": fetched}
            return result

    def meta(self):
        return getattr(self.metadata, "value", {"cached": False, "fetched_at_utc": datetime.now(timezone.utc).isoformat()})

    def list_activities(self, start_date, end_date, activity_type=None, limit=20, cursor=0):
        validate_range(start_date, end_date)
        if not 1 <= limit <= 50 or not 0 <= cursor <= 10000:
            raise ValueError("Limit must be 1–50 and cursor 0–10000")
        if activity_type not in (None, "running", "cycling", "swimming", "walking", "strength_training"):
            raise ValueError("Unsupported activity type filter")
        params = {"startDate": start_date, "endDate": end_date, "start": cursor, "limit": limit + 1}
        if activity_type:
            params["activityType"] = "fitness_equipment" if activity_type == "strength_training" else activity_type
            if activity_type == "strength_training":
                params["activitySubType"] = activity_type
        raw = self.call("connectapi", "/activitylist-service/activities/search/activities", params=params)
        if not isinstance(raw, list) or len(raw) > limit + 1:
            raise ValueError("Invalid activity page")
        return {"activities": [activity(item) for item in raw[:limit]],
                "next_cursor": cursor + limit if len(raw) > limit else None,
                "start_date": start_date, "end_date": end_date,
                **self.meta()}

    def get_activity(self, activity_id):
        return {"activity": activity(self.call("get_activity", validate_id(activity_id))),
                **self.meta()}

    def get_activity_splits(self, activity_id):
        return {**splits(self.call("get_activity_splits", validate_id(activity_id))), **self.meta()}

    def get_activity_samples(self, activity_id, metric="heart_rate", max_points=200):
        validate_id(activity_id)
        if metric != "heart_rate" or not 1 <= max_points <= 1000:
            raise ValueError("Only heart_rate with 1–1000 points is supported")
        return {**heart_rate_samples(self.call("get_activity_details", activity_id, maxchart=max_points, maxpoly=0), max_points), **self.meta()}

    def get_strength_sets(self, activity_id):
        return {**strength_sets(self.call("get_activity_exercise_sets", validate_id(activity_id))), **self.meta()}

    def get_training_summary(self, start_date, end_date):
        validate_range(start_date, end_date)
        rows, seen, cursor = [], set(), 0
        complete = False
        cache_flags, source_times = [], []
        deadline = time.monotonic() + 120
        for _ in range(10):
            if time.monotonic() > deadline:
                break
            page = self.list_activities(start_date, end_date, limit=50, cursor=cursor)
            cache_flags.append(page.get("cached", False))
            source_times.append(page.get("fetched_at_utc"))
            for row in page["activities"]:
                if row["activity_id"] not in seen:
                    rows.append(row)
                    seen.add(row["activity_id"])
            if page["next_cursor"] is None:
                complete = True
                break
            cursor = page["next_cursor"]
        def total(key):
            valid = [row[key] for row in rows if row[key] is not None]
            return {"value": sum(valid) if valid or not rows else None,
                    "activities_with_metric": len(valid), "activities_missing_metric": len(rows)-len(valid)}
        return {"start_date": start_date, "end_date": end_date, "activity_count": len(rows),
                "coverage_complete": complete, "continuation_cursor": None if complete else cursor,
                "distance_m": total("distance_m"), "duration_s": total("duration_s"),
                "totals_are_partial": not complete,
                "by_activity_type": {kind: sum((row["activity_type"] or "unknown") == kind for row in rows)
                                     for kind in {row["activity_type"] or "unknown" for row in rows}},
                "computed_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_fetched_at_utc": source_times, "includes_cached_pages": any(cache_flags)}

