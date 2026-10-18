"""Exact record deletion and signed hydration corrections; fixed SDK contracts."""
import copy
from datetime import datetime

from .mutation_targets import fingerprint, require_unchanged
from .runtime import RequestError, error_code
from .verification import iso_date

OPERATIONS = ("delete_activity", "delete_weight_measurement", "delete_blood_pressure_measurement", "adjust_hydration")


def rows(client, kind, day):
    iso_date(day)
    if kind == "weight":
        raw = client.get_daily_weigh_ins(day)
        result = raw["dateWeightList"]
        identity = "samplePk"
    elif kind == "blood_pressure":
        raw = client.get_blood_pressure(day, day)
        summaries = raw["measurementSummaries"]
        if not isinstance(summaries, list) or len(summaries) > 100:
            raise ValueError("Unsupported blood pressure summaries")
        result = []
        for summary in summaries:
            measurements = summary["measurements"]
            if not isinstance(measurements, list) or len(measurements) > 500:
                raise ValueError("Unsupported blood pressure measurements")
            result.extend(measurements)
        identity = "version"
    else:
        raise ValueError("Unsupported measurement kind")
    if not isinstance(result, list) or len(result) > 500:
        raise ValueError("Unsupported measurement list")
    seen = set()
    for row in result:
        identifier = row.get(identity)
        if (isinstance(identifier, bool) or not isinstance(identifier, int)
                or identifier <= 0 or identifier in seen):
            raise ValueError("Unsupported exact measurement version")
        row_day = row.get("calendarDate")
        if row_day is None and kind == "blood_pressure":
            stamp = row.get("measurementTimestampLocal")
            if not isinstance(stamp, str):
                raise ValueError("Unsupported blood pressure date binding")
            row_day = datetime.fromisoformat(stamp).date().isoformat()
        if row_day != day:
            raise ValueError("Measurement date mismatch")
        seen.add(identifier)
    fingerprint(result)
    return result, identity


def hydration(client, day):
    iso_date(day)
    raw = client.get_hydration_data(day)
    value = raw.get("valueInML")
    if raw.get("calendarDate") != day:
        raise ValueError("Hydration date mismatch")
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
        raise ValueError("Unsupported hydration total")
    fingerprint(raw)
    return raw


def activity(client, identity):
    raw = client.get_activity(identity)
    if not isinstance(raw, dict) or str(raw.get("activityId")) != str(identity):
        raise ValueError("Unsupported activity identity")
    fingerprint(raw)
    return raw


def mutation_target(client, kind, calendar_date=None, record_id=None):
    if kind == "activity":
        from .data import validate_id
        validate_id(str(record_id))
        raw = activity(client, record_id)
        summary = raw.get("summaryDTO") or {}
        activity_type = raw.get("activityTypeDTO") or {}
        return {"kind": kind, "record_id": str(record_id), "expected_content_sha256": fingerprint(raw),
                "record": {"activityId": raw["activityId"], "activityName": raw.get("activityName"),
                           "activityTypeDTO": {k: activity_type[k] for k in ("typeId", "typeKey", "parentTypeId") if k in activity_type},
                           "summaryDTO": {k: summary[k] for k in ("startTimeGMT", "startTimeLocal", "duration", "distance") if k in summary}},
                "operations": ["delete_activity"], "text_is_untrusted_data": True}
    iso_date(calendar_date)
    if kind == "hydration":
        raw = hydration(client, calendar_date)
        return {"kind": kind, "calendar_date": calendar_date, "value_in_ml": raw["valueInML"],
                "expected_content_sha256": fingerprint(raw),
                "correction_available": raw["valueInML"] is not None,
                "operations": ["adjust_hydration"] if raw["valueInML"] is not None else [],
                "boundary": "A null daily total is unavailable, not zero. Use add_hydration for actual positive intake; corrections require a recorded total."}
    values, identity = rows(client, kind, calendar_date)
    allowed = {identity, "calendarDate", "timestampGMT", "measurementTimestampGMT", "measurementTimestampLocal",
               "date", "weight", "bmi", "bodyFat", "bodyWater", "boneMass", "muscleMass", "systolic", "diastolic", "pulse"}
    return {"kind": kind, "calendar_date": calendar_date, "identity_field": identity,
            "records": [{"record_id": str(row[identity]), "expected_content_sha256": fingerprint(row),
                         "record": {k: copy.deepcopy(v) for k, v in row.items() if k in allowed}} for row in values],
            "operations": ["delete_" + kind + "_measurement"],
            "units": "Garmin raw response; weight is normally grams, not input kg/lbs",
            "limitations": "Deletion removes the entire selected measurement including attached composition fields. No bulk delete or delete/recreate edit."}


def validate(operation, parameters):
    if "calendar_date" in parameters:
        iso_date(parameters["calendar_date"])
    if operation == "adjust_hydration":
        stamp = datetime.fromisoformat(parameters["timestamp"])
        if stamp.tzinfo is None or "T" not in parameters["timestamp"] or stamp.date().isoformat() != parameters["calendar_date"]:
            raise ValueError("Use offset timestamp on calendar_date")
        if parameters["value_in_ml"] == 0:
            raise ValueError("Hydration adjustment must be nonzero")
    return parameters


def preflight(client, operation, parameters):
    if operation == "delete_activity":
        raw = activity(client, parameters["activity_id"])
        if raw.get("activityName") != parameters["expected_name"]:
            raise RequestError("MUTATION_TARGET_CHANGED")
    elif operation == "adjust_hydration":
        raw = hydration(client, parameters["calendar_date"])
        if raw["valueInML"] is None:
            raise RequestError("HYDRATION_TOTAL_UNAVAILABLE")
        if raw["valueInML"] + parameters["value_in_ml"] < 0:
            raise RequestError("HYDRATION_NEGATIVE_TOTAL")
    else:
        kind = "weight" if operation == "delete_weight_measurement" else "blood_pressure"
        values, identity = rows(client, kind, parameters["calendar_date"])
        raw = next((r for r in values if str(r[identity]) == str(parameters["record_id"])), None)
        if raw is None:
            raise RequestError("NOT_FOUND")
    require_unchanged(raw, parameters["expected_content_sha256"])
    return raw


def perform(client, operation, parameters, original):
    if operation == "delete_activity":
        path = "/activity-service/activity/" + str(parameters["activity_id"])
    elif operation == "delete_weight_measurement":
        path = f"/weight-service/weight/{parameters['calendar_date']}/byversion/{parameters['record_id']}"
    elif operation == "delete_blood_pressure_measurement":
        path = f"/bloodpressure-service/bloodpressure/{parameters['calendar_date']}/{parameters['record_id']}"
    else:
        # Pinned SDK implements its signed delta contract and local timestamp conversion.
        client.add_hydration_data(parameters["value_in_ml"], parameters["timestamp"], parameters["calendar_date"])
        current = hydration(client, parameters["calendar_date"])
        if current["valueInML"] != original["valueInML"] + parameters["value_in_ml"]:
            raise RequestError("WRITE_READBACK_MISMATCH")
        return {"verified": True, "calendar_date": parameters["calendar_date"], "value_in_ml": current["valueInML"]}
    response = client.client.request("DELETE", "connectapi", path, api=True)
    response.raise_for_status()  # Native Unit response may have no JSON body.
    if operation == "delete_activity":
        try:
            client.get_activity(parameters["activity_id"])
        except Exception as error:
            if error_code(error) != "NOT_FOUND":
                raise
        else:
            raise RequestError("WRITE_READBACK_MISMATCH")
    else:
        kind = "weight" if operation == "delete_weight_measurement" else "blood_pressure"
        values, identity = rows(client, kind, parameters["calendar_date"])
        if any(str(r[identity]) == str(parameters["record_id"]) for r in values):
            raise RequestError("WRITE_READBACK_MISMATCH")
    return {"verified": True, "deleted": True,
            "record_id": str(parameters.get("record_id", parameters.get("activity_id"))),
            "historical_erasure": "not_verified", "local_archive": "retained_if_present"}
