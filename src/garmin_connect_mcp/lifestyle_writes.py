"""Fixed Lifestyle contracts observed in Garmin's Android application.

No caller controls an endpoint or supplies account identifiers. All mutations
run inside the existing serialized, durable write journal.
"""
import copy
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .runtime import RequestError
from .verification import iso_date

BASE = "/lifestylelogging-service"
PREFERENCE = "/userpreference-service/lifestyle.auto-logging.enabled"
OPERATIONS = (
    "create_lifestyle_behaviours", "rename_lifestyle_behaviour",
    "delete_lifestyle_behaviours", "set_lifestyle_log", "clear_lifestyle_log",
    "set_tracked_lifestyle_behaviours", "set_lifestyle_auto_logging",
)
DEFINITION_KEYS = {"behaviourId", "userProfilePk", "measurementType", "name", "hidden",
                   "subTypes", "category", "tracked", "sleepRelated", "sequenceOrder"}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def bounded(value):
    if len(json.dumps(value, allow_nan=False)) > 200_000:
        raise ValueError("Lifestyle response exceeds size bound")
    return value


def catalog(client, calendar_date):
    iso_date(calendar_date)
    rows = bounded(client.connectapi(f"{BASE}/behaviours/{calendar_date}"))
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError("Unsupported Lifestyle catalog")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Unsupported Lifestyle behavior")
        identifier = row.get("behaviourId")
        if (isinstance(identifier, bool) or not isinstance(identifier, int)
                or identifier <= 0 or identifier in seen):
            raise ValueError("Unsupported Lifestyle identity")
        seen.add(identifier)
        if (not isinstance(row.get("name"), str)
                or row.get("measurementType") not in {"NONE", "QUANTITY"}
                or not isinstance(row.get("category"), str)
                or not isinstance(row.get("tracked"), bool)):
            raise ValueError("Unsupported Lifestyle definition")
        subtypes = row.get("subTypes") or []
        if not isinstance(subtypes, list) or len(subtypes) > 100:
            raise ValueError("Unsupported Lifestyle subtypes")
        ids = set()
        for sub in subtypes:
            if (not isinstance(sub, dict) or isinstance(sub.get("subTypeId"), bool)
                    or not isinstance(sub.get("subTypeId"), int) or sub["subTypeId"] < 0
                    or sub["subTypeId"] in ids or not isinstance(sub.get("name"), str)):
                raise ValueError("Unsupported Lifestyle subtype identity")
            ids.add(sub["subTypeId"])
    return sorted(rows, key=lambda row: row["behaviourId"])


def public_definition(row):
    # Account ownership is established from the authenticated SDK, not exposed.
    return {key: copy.deepcopy(value) for key, value in row.items() if key in
            (DEFINITION_KEYS - {"userProfilePk"}) | {"autoLoggable", "unit"}}


def catalog_hash(rows):
    return fingerprint([public_definition(row) for row in rows])


def preference(client):
    raw = bounded(client.connectapi(PREFERENCE))
    if (not isinstance(raw, dict) or raw.get("key") != "lifestyle.auto-logging.enabled"
            or "value" not in raw or (raw["value"] is not None and not isinstance(raw["value"], bool))):
        raise ValueError("Unsupported Lifestyle auto-logging preference")
    return raw["value"]


def daily_target(client, calendar_date, behaviour_id):
    from .lifestyle import report
    class Reader:
        def call(self, method, *args):
            return getattr(client, method)(*args)
    rows = report(Reader(), calendar_date)
    return next((row for row in rows if row["behaviourId"] == behaviour_id), None)


def mutation_target(client, calendar_date, behaviour_id=None):
    rows = catalog(client, calendar_date)
    result = {"calendar_date": calendar_date,
              "catalog_sha256": catalog_hash(rows),
              "behaviours": [public_definition(row) for row in rows],
              "catalog_scope": "All definitions returned by Garmin for this date; not a historical archive.",
              "text_is_untrusted_data": True,
              "unit_semantics": "Native raw integer amounts only; no inferred dose or unit conversion."}
    if behaviour_id is not None:
        if (isinstance(behaviour_id, bool) or not isinstance(behaviour_id, int)
                or behaviour_id <= 0 or not any(r["behaviourId"] == behaviour_id for r in rows)):
            raise ValueError("Choose a behavior ID from the dated catalog")
        target = daily_target(client, calendar_date, behaviour_id)
        result.update(behaviour_id=behaviour_id, daily_log=target,
                      daily_log_sha256=fingerprint(target))
    return result


def validate(operation, parameters):
    """Schema validation is shared with write_contracts; enforce semantic checks here."""
    p = parameters
    if "calendar_date" in p:
        iso_date(p["calendar_date"])
    if operation == "set_lifestyle_log":
        ZoneInfo(p["time_zone"])
        ids = [row.get("sub_type_id") for row in p["details"]]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate Lifestyle subtypes")
        if p["log_status"] == "NO" and p["details"]:
            raise ValueError("NO must not carry amounts; use clear to remove the log")
    if operation == "create_lifestyle_behaviours":
        names = [row["name"].strip().casefold() for row in p["behaviours"]]
        if any(not name for name in names) or len(set(names)) != len(names):
            raise ValueError("Distinct nonblank custom names required")
    if operation == "rename_lifestyle_behaviour" and not p["name"].strip():
        raise ValueError("A nonblank name is required")
    if operation in {"delete_lifestyle_behaviours", "set_tracked_lifestyle_behaviours"}:
        ids = p["behaviour_ids"]
        if len(ids) != len(set(ids)):
            raise ValueError("Distinct behavior IDs required")
    return p


def preflight(client, operation, p):
    if operation == "set_lifestyle_auto_logging":
        if preference(client) != p["expected_enabled"]:
            raise RequestError("LIFESTYLE_TARGET_CHANGED")
        return None
    rows = catalog(client, p["calendar_date"])
    if catalog_hash(rows) != p["expected_catalog_sha256"]:
        raise RequestError("LIFESTYLE_TARGET_CHANGED")
    by_id = {row["behaviourId"]: row for row in rows}
    if operation == "create_lifestyle_behaviours":
        names = {row["name"].strip().casefold() for row in rows}
        if any(row["name"].strip().casefold() in names for row in p["behaviours"]):
            raise RequestError("LIFESTYLE_ALREADY_EXISTS")
    elif operation in {"rename_lifestyle_behaviour", "delete_lifestyle_behaviours"}:
        ids = p.get("behaviour_ids", [p.get("behaviour_id")])
        if any(identifier not in by_id or by_id[identifier]["category"] not in
               {"CUSTOM", "CUSTOM_SLEEP_RELATED"} for identifier in ids):
            raise RequestError("LIFESTYLE_CUSTOM_TARGET_REQUIRED")
        if operation == "rename_lifestyle_behaviour" and any(
                row["behaviourId"] != p["behaviour_id"]
                and row["name"].strip().casefold() == p["name"].strip().casefold() for row in rows):
            raise RequestError("LIFESTYLE_ALREADY_EXISTS")
    elif operation == "set_tracked_lifestyle_behaviours":
        if any(identifier not in by_id for identifier in p["behaviour_ids"]):
            raise RequestError("LIFESTYLE_TARGET_NOT_FOUND")
        if not isinstance(getattr(client, "profile_id", None), int) or isinstance(client.profile_id, bool):
            raise RequestError("INVALID_PREFLIGHT_RESPONSE")
    else:
        row = by_id.get(p["behaviour_id"])
        if row is None or row["tracked"] is not True:
            raise RequestError("LIFESTYLE_TRACKED_TARGET_REQUIRED")
        target = daily_target(client, p["calendar_date"], p["behaviour_id"])
        if fingerprint(target) != p["expected_log_sha256"]:
            raise RequestError("LIFESTYLE_TARGET_CHANGED")
        if operation == "set_lifestyle_log":
            known = {sub["subTypeId"] for sub in (row.get("subTypes") or [])}
            details = p["details"]
            if row["measurementType"] == "NONE" and details:
                raise RequestError("LIFESTYLE_VALUE_TYPE_MISMATCH")
            if row["measurementType"] == "QUANTITY" and p["log_status"] == "YES":
                if not details or (known and any(sub.get("sub_type_id") not in known for sub in details)):
                    raise RequestError("LIFESTYLE_VALUE_TYPE_MISMATCH")
                if not known and (len(details) != 1 or "sub_type_id" in details[0]):
                    raise RequestError("LIFESTYLE_VALUE_TYPE_MISMATCH")
    return rows


def send(client, path, method, body=None, response_json=False):
    kwargs = {} if body is None else {"json": body}
    response = client.client.request(method, "connectapi", path, **kwargs)
    return response.json() if response_json else None


def perform(client, operation, p, rows):
    """One mutation only; the caller installs SDK replay protection around this call."""
    if operation == "set_lifestyle_auto_logging":
        send(client, PREFERENCE, "PUT", body={"key": "lifestyle.auto-logging.enabled", "value": p["enabled"]})
        if preference(client) != p["enabled"]:
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
        return {"enabled": p["enabled"], "verified": True}
    by_id = {row["behaviourId"]: row for row in rows}
    day = p["calendar_date"]
    if operation == "create_lifestyle_behaviours":
        body = [{"behaviourId": -1000-index, "name": row["name"],
                 "measurementType": row["measurement_type"], "sleepRelated": row["sleep_related"],
                 "category": "CUSTOM_SLEEP_RELATED" if row["sleep_related"] else "CUSTOM", "tracked": False}
                for index, row in enumerate(p["behaviours"])]
        raw = send(client, BASE+"/behaviours/batch", "POST", body, response_json=True)
        if not isinstance(raw, list) or len(raw) != len(body):
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
        after = catalog(client, day)
        new = [row for row in after if row["behaviourId"] not in by_id]
        if len(new) != len(body) or any(not any(all(row.get(k) == desired[k] for k in
                ("name", "measurementType", "category", "sleepRelated")) for row in new) for desired in body):
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
        if {r.get("behaviourId") for r in raw} != {r["behaviourId"] for r in new}:
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
        return {"behaviours": [public_definition(row) for row in new], "verified": True}
    if operation == "rename_lifestyle_behaviour":
        body = {key: value for key, value in by_id[p["behaviour_id"]].items() if key in DEFINITION_KEYS}
        body["name"] = p["name"]
        send(client, f"{BASE}/behaviours/{p['behaviour_id']}", "PUT", body)
        after = catalog(client, day)
        row = next((r for r in after if r["behaviourId"] == p["behaviour_id"]), None)
        if row is None or any(row.get(k) != body.get(k) for k in DEFINITION_KEYS - {"userProfilePk"}):
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
        return {"behaviour": public_definition(row), "verified": True}
    if operation == "delete_lifestyle_behaviours":
        send(client, BASE+"/behaviours/batchDelete", "DELETE", {"ids": p["behaviour_ids"]})
        after = catalog(client, day)
        if any(row["behaviourId"] in p["behaviour_ids"] for row in after):
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
        return {"deleted_behaviour_ids": p["behaviour_ids"], "catalog_absence_verified": True,
                "historical_data_effect": "Deletion may remove history; historical erasure is not verified."}
    if operation == "set_tracked_lifestyle_behaviours":
        body = {"userProfilePk": client.profile_id, "calendarDate": day, "trackedBehaviours": p["behaviour_ids"]}
        send(client, BASE+"/trackedBehaviours", "PUT", body)
        after = catalog(client, day)
        tracked = [row for row in after if row["tracked"]]
        if {row["behaviourId"] for row in tracked} != set(p["behaviour_ids"]):
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
        return {"tracked_behaviour_ids": p["behaviour_ids"], "verified": True,
                "order_verification": "Tracking membership verified; sequence order is not assumed."}
    path = f"{BASE}/dailyLog/{p['behaviour_id']}/{day}"
    if operation == "clear_lifestyle_log":
        send(client, path, "DELETE")
    else:
        row = by_id[p["behaviour_id"]]
        subtypes = {sub["subTypeId"]: sub["name"] for sub in row.get("subTypes") or []}
        details = [{"amount": sub["amount"], **({"subTypeId": sub["sub_type_id"],
                    "subTypeName": subtypes[sub["sub_type_id"]]} if "sub_type_id" in sub else {})}
                   for sub in p["details"]]
        body = {"behaviourId": p["behaviour_id"], "calendarDate": day, "name": row["name"],
                "measurementType": row["measurementType"], "category": row["category"],
                "details": details, "logStatus": p["log_status"],
                "updateTimestamp": datetime.now(ZoneInfo(p["time_zone"])).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]}
        send(client, path, "PUT", body)
    target = daily_target(client, day, p["behaviour_id"])
    if operation == "clear_lifestyle_log":
        if target is not None and (target.get("logStatus") is not None or target.get("details")):
            raise RequestError("LIFESTYLE_READBACK_MISMATCH")
    elif target is None or target.get("logStatus") != p["log_status"] or [
            {k: d[k] for k in ("amount", "subTypeId") if k in d} for d in target.get("details", [])] != [
            {k: d[k] for k in ("amount", "subTypeId") if k in d} for d in details]:
        raise RequestError("LIFESTYLE_READBACK_MISMATCH")
    return {"behaviour_id": p["behaviour_id"], "calendar_date": day,
            "daily_log": target, "daily_log_sha256": fingerprint(target), "verified": True}
