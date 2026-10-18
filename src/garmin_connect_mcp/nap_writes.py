"""Current-day nap editing from fixed Android routes and DTO evidence."""
import copy
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import sleep_writes
from .mutation_targets import fingerprint, require_unchanged
from .runtime import RequestError
from .verification import iso_date

OPERATIONS = ("add_nap", "update_nap", "delete_nap")
BASE = sleep_writes.BASE


def now():
    return datetime.now(timezone.utc)


def epoch(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("Unsupported native GMT timestamp")
    return int(parsed.replace(tzinfo=timezone.utc).timestamp() * 1000)


def current_day(day, time_zone):
    iso_date(day)
    if now().astimezone(ZoneInfo(time_zone)).date().isoformat() != day:
        raise ValueError("Garmin nap edits are limited to the current local calendar day")


def read(client, day):
    iso_date(day)
    rows = client.connectapi(BASE + "/naps/" + day, params={"includeOverlaps": True})
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Unsupported nap list")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or row.get("calendarDate") != day
                or str(row.get("userProfilePK")) != str(client.profile_id)):
            raise ValueError("Unsupported nap identity")
        start, end = epoch(row["napStartTimestampGMT"]), epoch(row["napEndTimestampGMT"])
        if start in seen or end <= start:
            raise ValueError("Unsupported nap timestamps")
        seen.add(start)
    rows = sorted(rows, key=lambda row: epoch(row["napStartTimestampGMT"]))
    fingerprint(rows)
    return rows


def mutation_target(client, calendar_date, time_zone):
    current_day(calendar_date, time_zone)
    rows = read(client, calendar_date)
    return {"calendar_date": calendar_date, "time_zone": time_zone,
            "expected_content_sha256": fingerprint(rows),
            "naps": [{"nap_start_ms": epoch(row["napStartTimestampGMT"]),
                      "nap_end_ms": epoch(row["napEndTimestampGMT"]),
                      **{k: row.get(k) for k in ("napTimeSec", "napStartTimestampGMT", "napEndTimestampGMT",
                                                "napStartTimeOffset", "napEndTimeOffset", "napSource")}} for row in rows],
            "timestamp_units": "GMT milliseconds for identity; offset minutes in native data",
            "operations": list(OPERATIONS), "limitations": "Current day only, 5 minutes to 3 hours; no overlap with main sleep or another nap. Native contract observed; live writes unverified."}


def validate(operation, parameters):
    current_day(parameters["calendar_date"], parameters["time_zone"])
    if operation != "delete_nap":
        _, _, duration = sleep_writes.times(parameters)
        if not 300 <= duration <= 10800 or datetime.fromisoformat(parameters["start_time"]).date().isoformat() != parameters["calendar_date"]:
            raise ValueError("Nap must be 5 minutes to 3 hours on the current calendar day")
    return parameters


def preflight(client, operation, parameters):
    validate(operation, parameters)  # Recheck midnight eligibility immediately before mutation.
    rows = read(client, parameters["calendar_date"])
    require_unchanged(rows, parameters["expected_content_sha256"])
    selected = None
    if operation != "add_nap":
        selected = next((row for row in rows if epoch(row["napStartTimestampGMT"]) == parameters["nap_start_ms"]), None)
        if selected is None:
            raise RequestError("MUTATION_TARGET_CHANGED")
    sleep = sleep_writes.read(client, parameters["calendar_date"])
    if operation != "delete_nap":
        start, end, _ = sleep_writes.times(parameters)
        intervals = [(epoch(r["napStartTimestampGMT"]), epoch(r["napEndTimestampGMT"])) for r in rows if r is not selected]
        intervals.append((sleep["sleepStartTimestampGMT"], sleep["sleepEndTimestampGMT"]))
        if any(start < b and end > a for a, b in intervals):
            raise RequestError("NAP_OVERLAP")
    return selected, sleep


def perform(client, operation, parameters, state):
    current_day(parameters["calendar_date"], parameters["time_zone"])
    selected, sleep = state
    day = parameters["calendar_date"]
    path = BASE + "/nap"
    if operation == "delete_nap":
        old_start = epoch(selected["napStartTimestampGMT"])
        method, path, body = "DELETE", path + f"/{day}/{old_start}", None
    else:
        start, end, duration = sleep_writes.times(parameters)
        body = copy.deepcopy(selected) if selected else {
            "userProfilePK": client.profile_id,
            "deviceId": (sleep.get("sleepNeed") or {}).get("deviceId", 0), "calendarDate": day}
        body.update(napTimeSec=duration, napSource=2,
                    napStartTimestampGMT=datetime.fromtimestamp(start / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    napEndTimestampGMT=datetime.fromtimestamp(end / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    napStartTimeOffset=int(datetime.fromisoformat(parameters["start_time"]).utcoffset().total_seconds() / 60),
                    napEndTimeOffset=int(datetime.fromisoformat(parameters["end_time"]).utcoffset().total_seconds() / 60))
        method = "POST" if operation == "add_nap" else "PUT"
        if selected:
            old_start, old_end = epoch(selected["napStartTimestampGMT"]), epoch(selected["napEndTimestampGMT"])
            path += f"/{day}/{old_start}/{old_end}"
    response = client.client.request(method, "connectapi", path, **({"json": body} if body else {}))
    response.raise_for_status()
    rows = read(client, day)
    if operation == "delete_nap":
        verified = not any(epoch(row["napStartTimestampGMT"]) == old_start for row in rows)
    else:
        matches = [r for r in rows if epoch(r["napStartTimestampGMT"]) == start]
        verified = len(matches) == 1 and all(matches[0].get(k) == body[k] for k in (
            "napStartTimestampGMT", "napEndTimestampGMT", "napTimeSec", "napStartTimeOffset", "napEndTimeOffset", "napSource"))
        if selected and old_start != start:
            verified = verified and not any(epoch(r["napStartTimestampGMT"]) == old_start for r in rows)
    if not verified:
        raise RequestError("WRITE_READBACK_MISMATCH")
    return {"calendar_date": day, "verified": True, "expected_content_sha256": fingerprint(rows)}
