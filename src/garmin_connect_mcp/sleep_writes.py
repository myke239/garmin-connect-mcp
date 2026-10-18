"""Fixed Garmin Android 5.30.1 sleep contracts, with fresh snapshot guards.

Time editing mirrors the native DTO copy: duration, confirmed and GMT endpoints
change; original local endpoints, stage data and confirmation type are preserved.
No score/stage inputs or caller-supplied native DTO are accepted.
"""
import copy
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .mutation_targets import fingerprint, require_unchanged
from .runtime import RequestError
from .verification import iso_date

BASE = "/sleep-service/sleep"
NATIVE_KEYS = frozenset(['autoSleepEndTimestampGMT',
 'autoSleepStartTimestampGMT',
 'averageRespirationValue',
 'averageSpO2HRSleep',
 'averageSpO2Value',
 'avgHeartRate',
 'avgSleepStress',
 'awakeCount',
 'awakeSleepSeconds',
 'breathingDisruptionSeverity',
 'calendarDate',
 'dailyNapDTOS',
 'deepSleepSeconds',
 'deviceRemCapable',
 'highestRespirationValue',
 'highestSpO2Value',
 'id',
 'lightSleepSeconds',
 'lowestRespirationValue',
 'lowestSpO2Value',
 'napTimeSeconds',
 'nextSleepNeed',
 'remSleepSeconds',
 'retro',
 'sleepAlignment',
 'sleepEndTimestampGMT',
 'sleepEndTimestampLocal',
 'sleepFromDevice',
 'sleepNeed',
 'sleepQualityTypePK',
 'sleepResultTypePK',
 'sleepScoreFeedback',
 'sleepScoreInsight',
 'sleepScorePersonalizedInsight',
 'sleepScores',
 'sleepStartTimestampGMT',
 'sleepStartTimestampLocal',
 'sleepTimeSeconds',
 'sleepVersion',
 'sleepWindowConfirmationType',
 'sleepWindowConfirmed',
 'spo2Threshold',
 'unmeasurableSleepSeconds',
 'userNote',
 'userProfilePK'])
OPERATIONS = ("add_sleep", "update_sleep_times", "set_sleep_note", "clear_sleep_note")


def read_optional(client, calendar_date):
    from .data import validate_id
    validate_id(str(client.profile_id))
    iso_date(calendar_date)
    raw = client.connectapi(BASE + "/dailySleepData", params={
        "date": calendar_date, "nonSleepBufferMinutes": 60})
    if not isinstance(raw, dict) or "dailySleepDTO" not in raw:
        raise ValueError("Unsupported sleep response")
    row = raw.get("dailySleepDTO")
    if row is None:
        return None
    if (isinstance(row, dict) and not isinstance(row.get("id"), bool) and row.get("id") in (-1, 0)
            and row.get("sleepStartTimestampGMT") == 0
            and row.get("sleepEndTimestampGMT") == 0
            and row.get("calendarDate") in (None, calendar_date)
            and str(row.get("userProfilePK")) in ("0", str(client.profile_id))):
        return None
    if not isinstance(row, dict) or row.get("calendarDate") != calendar_date:
        raise ValueError("Unsupported dated sleep response")
    if (isinstance(row.get("id"), bool) or not isinstance(row.get("id"), int)
            or row["id"] <= 0 or str(row.get("userProfilePK")) != str(client.profile_id)):
        raise ValueError("Unsupported sleep identity")
    fingerprint(row)  # Bound response and reject nonfinite values before use.
    return row


def read(client, calendar_date):
    row = read_optional(client, calendar_date)
    if row is None:
        raise RequestError("NOT_FOUND")
    return row


def snapshot(row, day):
    return row if row is not None else {"calendar_date": day, "main_sleep_absent": True}


def mutation_target(client, calendar_date):
    row = read_optional(client, calendar_date)
    return {"calendar_date": calendar_date, "sleep_exists": row is not None,
            "sleep_id": str(row["id"]) if row else None,
            "expected_content_sha256": fingerprint(snapshot(row, calendar_date)),
            "sleep": {k: copy.deepcopy(row[k]) for k in (
                "sleepStartTimestampGMT", "sleepEndTimestampGMT", "sleepTimeSeconds",
                "sleepWindowConfirmed", "sleepWindowConfirmationType", "userNote") if row and k in row},
            "timestamp_units": "milliseconds since Unix epoch (GMT)",
            "operations": list(OPERATIONS[1:]) if row else ["add_sleep"], "text_is_untrusted_data": True,
            "limitations": "No sleep deletion, stage/score setter or device sleep-schedule change. Time edits preserve native recorded metadata; Garmin recalculation is separate."}


def times(parameters):
    zone = ZoneInfo(parameters["time_zone"])
    values = []
    for field in ("start_time", "end_time"):
        stamp = parameters[field]
        parsed = datetime.fromisoformat(stamp)
        if parsed.tzinfo is None or "T" not in stamp or parsed.microsecond:
            raise ValueError("Use whole-second ISO timestamps with explicit offsets")
        # An explicit offset resolves fallback ambiguity; a gap/wrong offset fails roundtrip.
        local = parsed.astimezone(zone)
        if local.replace(tzinfo=None) != parsed.replace(tzinfo=None) or local.utcoffset() != parsed.utcoffset():
            raise ValueError("Timestamp offset does not match IANA timezone")
        values.append(parsed)
    start, end = values
    duration = int((end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds())
    if not 60 <= duration <= 86400 or end.date().isoformat() != parameters["calendar_date"]:
        raise ValueError("Sleep must last 1 minute to 24 hours and end on calendar_date")
    if end > datetime.now(timezone.utc):
        raise ValueError("Sleep must have finished")
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000), duration


def validate(operation, parameters):
    iso_date(parameters["calendar_date"])
    if operation in {"add_sleep", "update_sleep_times"}:
        times(parameters)
    return parameters


def preflight(client, operation, parameters):
    row = read_optional(client, parameters["calendar_date"])
    require_unchanged(snapshot(row, parameters["calendar_date"]), parameters["expected_content_sha256"])
    if operation == "add_sleep":
        if row is not None:
            raise RequestError("MUTATION_TARGET_CHANGED")
        return None
    if row is None or str(row["id"]) != str(parameters["sleep_id"]):
        raise RequestError("MUTATION_TARGET_CHANGED")
    return row


def perform(client, operation, parameters, row):
    day = parameters["calendar_date"]
    if operation in {"add_sleep", "update_sleep_times"}:
        start, end, duration = times(parameters)
        # Native new-record DTO defaults. Zero stage fields denote unavailable,
        # not estimated stages; Garmin's manual entry creates duration only.
        body = {k: copy.deepcopy(v) for k, v in row.items() if k in NATIVE_KEYS} if row else {
            "id": -1, "userProfilePK": client.profile_id, "calendarDate": day,
            "sleepTimeSeconds": 0, "napTimeSeconds": 0,
            "sleepWindowConfirmed": False, "sleepStartTimestampGMT": 0, "sleepEndTimestampGMT": 0,
            "sleepStartTimestampLocal": 0, "sleepEndTimestampLocal": 0,
            "unmeasurableSleepSeconds": 0, "deepSleepSeconds": 0, "lightSleepSeconds": 0,
            "remSleepSeconds": 0, "awakeSleepSeconds": 0, "deviceRemCapable": False, "sleepFromDevice": False}
        body.update(sleepStartTimestampGMT=start, sleepEndTimestampGMT=end,
                    sleepTimeSeconds=duration, sleepWindowConfirmed=True)
        method = "PUT" if row else "POST"
        path = BASE + "/dailySleep" + ("/" + str(row["id"]) if row else "")
        expected = {k: body[k] for k in ("sleepStartTimestampGMT", "sleepEndTimestampGMT", "sleepWindowConfirmed")}
    elif operation == "set_sleep_note":
        method, path, body = "PUT", BASE + "/dailySleep/" + day + "/note", {"userNote": parameters["note"]}
        expected = {"userNote": parameters["note"]}
    elif operation == "clear_sleep_note":
        method, path, body = "DELETE", BASE + "/dailySleep/" + day + "/note", None
        expected = {"userNote": None}
    else:
        raise ValueError("Unsupported sleep operation")
    kwargs = {"json": body} if body is not None else {}
    response = client.client.request(method, "connectapi", path, **kwargs)
    response.raise_for_status()  # Native routes return Unit/204: do not require JSON.
    current = read(client, day)
    if any(current.get(k) != v for k, v in expected.items()):
        raise RequestError("WRITE_READBACK_MISMATCH")
    return {"calendar_date": day, "sleep_id": str(current["id"]), "verified": True,
            "verified_fields": list(expected), "recalculated_metrics": "not_verified",
            "expected_content_sha256": fingerprint(current)}
