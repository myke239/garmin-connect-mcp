"""Default-enabled, previewed account writes with a durable at-most-once journal."""
import argparse
import base64
import hashlib
import inspect
import json
import math
import secrets
import tempfile
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Literal,Any,Callable

from .auth import TokenStore, data_directory
from .runtime import RequestError, session_lock, bounded_request, error_code

METHODS = {
    "create_workout": "upload_workout", "update_workout": "update_workout",
    "schedule_workout": "schedule_workout", "unschedule_workout": "unschedule_workout",
    "send_workout_to_device": "push_workout_to_device",
    "create_manual_activity": "create_manual_activity", "upload_activity_file": "upload_activity",
    "set_activity_name": "set_activity_name", "set_activity_description": "set_activity_description",
    "set_activity_type": "set_activity_type", "replace_strength_sets": "set_activity_exercise_sets",
    "add_weight": "add_weigh_in", "add_body_composition": "add_body_composition",
    "add_hydration": "add_hydration_data", "add_blood_pressure": "set_blood_pressure",
}
from .lifestyle_writes import OPERATIONS as LIFESTYLE_OPERATIONS
from .extended_writes import OPERATIONS as EXTENDED_OPERATIONS

OPERATIONS = EXTENDED_OPERATIONS + LIFESTYLE_OPERATIONS + tuple(METHODS) + ("create_training_calendar", "rename_workout", "delete_workout", "schedule_existing_workouts")
WriteOperation = Literal["create_workout", "update_workout", "schedule_workout", "unschedule_workout",
    "send_workout_to_device", "create_manual_activity", "upload_activity_file", "set_activity_name",
    "set_activity_description", "set_activity_type", "replace_strength_sets", "add_weight",
    "add_body_composition", "add_hydration", "add_blood_pressure", "create_training_calendar",
    "rename_workout", "delete_workout", "schedule_existing_workouts",
    "create_lifestyle_behaviours", "rename_lifestyle_behaviour", "delete_lifestyle_behaviours",
    "set_lifestyle_log", "clear_lifestyle_log", "set_tracked_lifestyle_behaviours", "set_lifestyle_auto_logging", "update_sleep_times", "set_sleep_note", "clear_sleep_note", "add_sleep", "add_nap", "update_nap", "delete_nap", "delete_activity",
    "delete_weight_measurement", "delete_blood_pressure_measurement", "adjust_hydration"]
from .sport_schemas import SPORT_IDS,manual_type_supported
SPORTS = set(SPORT_IDS)


class WriteInputError(ValueError):
    """Locally generated guidance; excludes free text, secrets and upstream errors."""
    def __init__(self, operation, message):
        self.operation = operation
        super().__init__(message)


def validate_schedule(parameters):
    if set(parameters) != {"workout_id", "date_str"}:
        raise WriteInputError("schedule_workout",
            "Use exactly workout_id and date_str. workoutId and date are not SDK parameter names.")
    workout_id = parameters["workout_id"]
    if (isinstance(workout_id, bool) or not isinstance(workout_id, (int, str))
            or not str(workout_id).isascii() or not str(workout_id).isdigit() or int(workout_id) <= 0):
        raise WriteInputError("schedule_workout", "workout_id must be a positive integer or a string of ASCII digits.")
    value = parameters["date_str"]
    try:
        if not isinstance(value, str) or len(value) != 10 or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError:
        raise WriteInputError("schedule_workout", "date_str must be a valid calendar date formatted YYYY-MM-DD.") from None


def validate_workout(payload):
    location = "workout_json"

    def invalid(message):
        return WriteInputError("create_workout", f"{location}: {message}")

    def enum(value, id_name, key_name):
        if (not isinstance(value, dict) or not isinstance(value.get(id_name), int)
                or isinstance(value.get(id_name), bool) or value[id_name] < 1
                or not isinstance(value.get(key_name), str) or not value[key_name]):
            raise invalid(f"Workout {key_name} requires its numeric {id_name} and string key")
        mappings={"sportTypeKey":SPORT_IDS,
            "stepTypeKey":{"warmup":1,"cooldown":2,"interval":3,"recovery":4,"rest":5,"repeat":6,"other":7,"main":8},
            "conditionTypeKey":{"lap.button":1,"time":2,"distance":3,"calories":4,"power":5,"heart.rate":6,"iterations":7,"fixed.rest":8,"fixed.repetition":9,"reps":10},
            "workoutTargetTypeKey":{"no.target":1,"power.zone":2,"cadence":3,"heart.rate.zone":4,"speed.zone":5,"pace.zone":6,"grade":7,"heart.rate.lap":8,"power.lap":9,"resistance":15}}
        if key_name == "sportTypeKey" and value[key_name] not in SPORT_IDS:
            raise WriteInputError("create_workout", "Each segment must use a supported Garmin workout sport; unsupported legacy enums lose identity.")
        known=mappings.get(key_name,{})
        if value[key_name] not in known or value[id_name] != known[value[key_name]]:
            raise invalid("Workout enum ID does not match its SDK key")

    enum(payload.get("sportType"), "sportTypeId", "sportTypeKey")
    total = 0
    seen_orders=set()
    seen_group_ids=set()
    last_order = 0

    def steps(items, depth=0, sport=None, path="workoutSteps"):
        nonlocal total, location, last_order
        location = path
        if not isinstance(items, list) or not 1 <= len(items) <= 100 or depth > 5:
            raise invalid("Provide 1–100 steps per group, with at most five nested repeat groups")
        for index, step in enumerate(items):
            location = f"{path}[{index}]"
            total += 1
            if total > 100 or not isinstance(step, dict):
                raise invalid("Workout requires at most 100 total steps")
            if not isinstance(step.get("stepOrder"), int) or isinstance(step["stepOrder"], bool) or step["stepOrder"] < 1:
                raise invalid("Each workout step requires positive stepOrder")
            if step["stepOrder"] in seen_orders:
                raise invalid("stepOrder values must be unique across every segment and nested step")
            if step["stepOrder"] <= last_order:
                raise invalid("stepOrder must increase in execution-tree order across segments and nested steps")
            last_order = step["stepOrder"]
            seen_orders.add(step["stepOrder"])
            enum(step.get("stepType"), "stepTypeId", "stepTypeKey")
            for field in ("targetValueOne","targetValueTwo","secondaryTargetValueOne","secondaryTargetValueTwo","weightValue"):
                value=step.get(field)
                if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):
                    raise invalid("Workout target/load values must be finite nonnegative numbers")
            if step.get("targetValueOne") is not None and step.get("targetValueTwo") is not None and step["targetValueOne"]>step["targetValueTwo"]:
                raise invalid("Workout targetValueOne must not exceed targetValueTwo; pace ranges use metres/second")
            if step.get("category") is not None:
                from garminconnect.exercises import CATEGORIES,EXERCISES
                if step["category"]=="POSE":
                    from .yoga import POSES
                    if (sport!="yoga" or step.get("exerciseName") not in POSES
                            or step.get("type")!="ExecutableStepDTO"
                            or step.get("stepType",{}).get("stepTypeKey")!="interval"
                            or step.get("endCondition",{}).get("conditionTypeKey")!="time"
                            or step.get("targetType",{}).get("workoutTargetTypeKey")!="no.target"
                            or isinstance(step.get("endConditionValue"),bool)
                            or not isinstance(step.get("endConditionValue"),(int,float))
                            or not 1<=step["endConditionValue"]<=86400
                            or not float(step["endConditionValue"]).is_integer()
                            or any(step.get(field) is not None for field in ("weightValue","targetValueOne","targetValueTwo","secondaryTargetType","secondaryTargetValueOne","secondaryTargetValueTwo"))):
                        raise WriteInputError("create_workout","POSE requires an exact verified identifier in a yoga segment and a timed untargeted interval of 1-86400 whole seconds. Use build_garmin_yoga_step.")
                elif step["category"] not in CATEGORIES:
                    raise invalid("Unknown Garmin exercise category")
                name=step.get("exerciseName")
                if step["category"]!="POSE" and name and not any(e["category"]==step["category"] and e["exercise"]==name for e in EXERCISES):
                    raise invalid("Exercise name does not match its Garmin category")
            if step.get("type") == "RepeatGroupDTO":
                count = step.get("numberOfIterations")
                if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 100:
                    raise invalid("Repeat groups require 1–100 iterations")
                if step["stepType"].get("stepTypeKey") != "repeat":
                    raise invalid("Repeat groups require the repeat step type")
                enum(step.get("endCondition"), "conditionTypeId", "conditionTypeKey")
                if step["endCondition"]["conditionTypeKey"] != "iterations":
                    raise invalid("Repeat groups require endCondition 7 / iterations")
                value = step.get("endConditionValue")
                if value is not None and (isinstance(value, bool) or value != count):
                    raise invalid("Repeat endConditionValue must equal numberOfIterations")
                if "skipLastRestStep" in step and not isinstance(step["skipLastRestStep"], bool):
                    raise invalid("skipLastRestStep must be boolean")
                group_location = location
                steps(step.get("workoutSteps"), depth + 1, sport, location + ".workoutSteps")
                location = group_location
                if step.get("skipLastRestStep") and step["workoutSteps"][-1]["stepType"]["stepTypeKey"] not in {"rest", "recovery"}:
                    raise invalid("skipLastRestStep requires a final rest or recovery child")
                group_id = step.get("childStepId")
                if group_id is not None:
                    if isinstance(group_id, bool) or not isinstance(group_id, int) or group_id < 1:
                        raise invalid("Repeat childStepId must be a positive integer")
                    if group_id in seen_group_ids:
                        raise invalid("Repeat groups require distinct childStepId values")
                    seen_group_ids.add(group_id)
                    if any(isinstance(child.get("childStepId"), bool) or child.get("childStepId") not in (None, group_id) for child in step["workoutSteps"] if child["type"] == "ExecutableStepDTO"):
                        raise invalid("Executable childStepId must match its repeat group")
            elif step.get("type") == "ExecutableStepDTO":
                if step["stepType"]["stepTypeKey"] == "repeat":
                    raise invalid("Repeat step types require RepeatGroupDTO")
                enum(step.get("endCondition"), "conditionTypeId", "conditionTypeKey")
                enum(step.get("targetType"), "workoutTargetTypeId", "workoutTargetTypeKey")
                if step.get("zoneNumber") is not None and (isinstance(step["zoneNumber"], bool) or
                        not isinstance(step["zoneNumber"], int) or not 1 <= step["zoneNumber"] <= 5):
                    raise invalid("zoneNumber must be a whole zone 1-5")
                if step.get("zoneNumber") is not None and any(step.get(k) is not None for k in ("targetValueOne", "targetValueTwo")):
                    raise invalid("Do not combine a named zone with a custom target range")
                if any(k in step["targetType"] for k in ("targetValueOne", "targetValueTwo", "zoneNumber")):
                    raise invalid("Place target values on the step, not inside targetType")
                if "conditionValue" in step["endCondition"]:
                    raise invalid("Put duration/distance in step.endConditionValue, not endCondition.conditionValue")
                if step["endCondition"]["conditionTypeKey"] in {"distance", "time"}:
                    value = step.get("endConditionValue")
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                        raise invalid("Time/distance steps require positive endConditionValue (seconds/metres)")
                if step["endCondition"]["conditionTypeKey"] == "reps":
                    value=step.get("endConditionValue")
                    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 1<=value<=1000 or not float(value).is_integer():
                        raise invalid("Rep-based steps require 1–1000 whole repetitions in endConditionValue")
            else:
                raise invalid("Use ExecutableStepDTO or RepeatGroupDTO")

    seen_segments = set()
    for index, segment in enumerate(payload["workoutSegments"]):
        location = f"workout_json.workoutSegments[{index}]"
        if not isinstance(segment, dict):
            raise invalid("Workout segments must be objects")
        order = segment.get("segmentOrder")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1 or order in seen_segments:
            raise invalid("Each segment requires a unique positive segmentOrder")
        seen_segments.add(order)
        enum(segment.get("sportType"), "sportTypeId", "sportTypeKey")
        if segment["sportType"]["sportTypeKey"] not in SPORTS:
            raise WriteInputError("create_workout","Each segment must use a supported Garmin workout sport; legacy walking/hiking workout enums lose their sport identity.")
        if payload["sportType"]["sportTypeKey"]!="multi_sport" and segment["sportType"]["sportTypeKey"]!=payload["sportType"]["sportTypeKey"]:
            raise invalid("Single-sport segments must match the workout sport")
        if payload["sportType"]["sportTypeKey"]=="multi_sport" and segment["sportType"]["sportTypeKey"]=="multi_sport":
            raise invalid("Multisport segments require explicit constituent sports")
        steps(segment.get("workoutSteps"), sport=segment["sportType"]["sportTypeKey"], path=location + ".workoutSteps")


def _validate(operation, parameters):
    """Validate a fixed SDK operation; never accept endpoints or local file paths."""
    from garminconnect import Garmin
    if operation not in OPERATIONS or not isinstance(parameters, dict):
        raise ValueError("Unsupported operation")
    parameters = json.loads(json.dumps(parameters, allow_nan=False))
    limit = (2 * 1024 * 1024 if operation == "replace_strength_sets" else
             256 * 1024 if operation in {"create_workout", "update_workout"} else
             2 * 1024 * 1024 if operation == "create_training_calendar" else 12000)
    if operation != "upload_activity_file" and len(json.dumps(parameters).encode("utf-8")) > limit:
        raise WriteInputError(operation, f"parameters: payload exceeds {limit} bytes")
    if operation in {"rename_workout", "delete_workout"}:
        from .data import validate_id
        validate_id(str(parameters["workout_id"]))
        if operation == "delete_workout" and parameters["confirm_calendar_removal"] is not True:
            raise WriteInputError(operation,"Explicit calendar-removal confirmation is required")
        return parameters
    if operation == "schedule_existing_workouts":
        keys=[]
        for item in parameters["workouts"]:
            validate_schedule(item)
            keys.append((str(item["workout_id"]),item["date_str"]))
        if len(keys)!=len(set(keys)):
            raise WriteInputError(operation,"Duplicate workout/date entries are forbidden")
        return parameters
    if operation == "schedule_workout":
        validate_schedule(parameters)
    if operation == "create_training_calendar":
        if set(parameters) != {"workouts"} or not 1 <= len(parameters["workouts"]) <= 20:
            raise ValueError("Provide 1–20 dated workout templates")
        for item in parameters["workouts"]:
            if set(item) != {"date", "workout"}:
                raise ValueError("Each entry needs date and workout")
            date.fromisoformat(item["date"])
            validate("create_workout", {"workout_json": item["workout"]})
        return parameters
    if operation == "upload_activity_file":
        if set(parameters) != {"format", "content_base64"} or parameters["format"] not in {"fit", "tcx", "gpx"}:
            raise ValueError("Provide format and base64 content; local paths are forbidden")
        try:
            content = base64.b64decode(parameters["content_base64"], validate=True)
        except (ValueError,TypeError):
            raise WriteInputError(operation,"content_base64 must contain valid base64-encoded file bytes") from None
        if not content or len(content) > 2 * 1024 * 1024:
            raise WriteInputError(operation,"Activity file must be 1 byte–2 MiB")
        if parameters["format"] == "fit":
            from garminconnect.fit import _calcCRC
            if len(content)<14 or content[0] not in (12,14) or content[8:12]!=b".FIT":
                raise WriteInputError(operation,"Invalid FIT header")
            size=int.from_bytes(content[4:8],"little")
            if len(content)!=content[0]+size+2:
                raise WriteInputError(operation,"FIT declared data length does not match file length")
            crc=0
            for byte in content: crc=_calcCRC(crc,byte)
            if crc!=0: raise WriteInputError(operation,"FIT file checksum is invalid")
            from .fit_support import decode
            try: decoded=decode(content)
            except RequestError:raise
            except ValueError:
                raise WriteInputError(operation,"FIT content is invalid or unsupported by the pinned Garmin FIT SDK") from None
            if decoded['file_type']!='activity' or not decoded['sessions'] or not decoded['laps'] or decoded['activities']!=1:
                raise WriteInputError(operation,"Only FIT activity recordings with session, lap and one activity message are accepted; health/course files are not activity uploads")
        if parameters["format"] != "fit":
            from defusedxml import ElementTree
            from defusedxml.common import DefusedXmlException
            from xml.etree.ElementTree import ParseError
            try: root = ElementTree.fromstring(content)
            except (DefusedXmlException,ParseError):
                raise WriteInputError(operation,"Activity XML is malformed or contains forbidden entities") from None
            expected = "gpx" if parameters["format"] == "gpx" else "TrainingCenterDatabase"
            if root.tag.split("}")[-1] != expected:
                raise ValueError("Invalid activity XML format")
            kind="trkpt" if parameters["format"]=="gpx" else "Trackpoint"
            points=[v for v in root.iter() if v.tag.split("}")[-1]==kind]
            if not 2<=len(points)<=25000:
                raise WriteInputError(operation,"Activity XML needs 2–25,000 timestamped track points")
            times=[]
            for point in points:
                field="time" if parameters["format"]=="gpx" else "Time"
                value=next((v.text for v in point if v.tag.split("}")[-1]==field),None)
                try:
                    parsed=datetime.fromisoformat(value)
                    if parsed.tzinfo is None: raise ValueError
                except (ValueError,TypeError):
                    raise WriteInputError(operation,"Every activity track point needs an ISO timestamp with timezone") from None
                times.append(parsed)
            if any(b<a for a,b in zip(times,times[1:])):
                raise WriteInputError(operation,"Activity track timestamps must not run backwards")
            if times[-1]<=times[0]:
                raise WriteInputError(operation,"Activity recording needs positive elapsed time")
        return parameters
    if operation in EXTENDED_OPERATIONS:
        from .extended_writes import validate as validate_extended
        return validate_extended(operation, parameters)
    if operation in LIFESTYLE_OPERATIONS:
        from .lifestyle_writes import validate as validate_lifestyle
        return validate_lifestyle(operation, parameters)
    method = METHODS[operation]
    try:
        inspect.signature(getattr(Garmin, method)).bind(None, **parameters)
    except TypeError:
        names = ", ".join(name for name in inspect.signature(getattr(Garmin, method)).parameters if name != "self")
        raise WriteInputError(operation, "Missing or unsupported SDK parameter names. Supported names: " + names) from None
    if operation in {"create_workout", "update_workout"}:
        payload = parameters["workout_json"]
        if not isinstance(payload, dict) or not isinstance(payload.get("workoutName"), str) or not payload["workoutName"].strip():
            raise ValueError("A named complete Garmin workout JSON template is required")
        if payload.get("sportType", {}).get("sportTypeKey") not in SPORTS:
            raise WriteInputError(operation,"Unsupported workout sport. Read list_garmin_workout_sports/get_garmin_workout_schema; legacy walking/hiking workout IDs lose their sport identity. Completed manual activity logs remain supported.")
        segments = payload.get("workoutSegments")
        if not isinstance(segments, list) or not 1 <= len(segments) <= 20:
            raise ValueError("Provide 1–20 workout segments")
        validate_workout(payload)
    for name, value in parameters.items():
        if name.endswith("_id"):
            if isinstance(value, bool) or not str(value).isdigit() or int(value) < (0 if name == "parent_type_id" else 1):
                raise ValueError("Explicit positive IDs required")
        if isinstance(value, str) and name != "workout_json" and len(value) > 2000:
            raise ValueError("Text too long")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Finite numbers required")
    if operation == "send_workout_to_device" and set(parameters) != {"workout_id", "device_id"}:
        raise ValueError("Specify both workout_id and device_id; no implicit device selection")
    for name in ("timestamp", "start_datetime"):
        if name in parameters:
            if not parameters[name]:
                raise ValueError("Provide an explicit timestamp")
            parsed = datetime.fromisoformat(parameters[name])
            if name == "timestamp" and parsed.tzinfo is None:
                raise ValueError("Timestamp needs a timezone offset")
            if name == "start_datetime":
                parameters[name]=parsed.isoformat(timespec="milliseconds")
    if operation in {"add_weight", "add_body_composition", "add_hydration", "add_blood_pressure", "create_manual_activity"}:
        required = "start_datetime" if operation == "create_manual_activity" else "timestamp"
        if required not in parameters:
            raise ValueError("Explicit timestamp required")
    if operation == "schedule_workout":
        date.fromisoformat(parameters["date_str"])
    if operation == "create_manual_activity":
        from zoneinfo import ZoneInfo
        ZoneInfo(parameters["time_zone"])
        for field in ("distance_km", "duration_min"):
            number = parameters[field]
            if isinstance(number, bool) or not isinstance(number, (int, float)) or number < 0 or (field == "duration_min" and number == 0):
                raise ValueError("Nonnegative distance and positive duration required")
    if operation in {"add_weight", "add_body_composition"}:
        weight = parameters["weight"]
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 < weight <= 1000:
            raise ValueError("Positive weight required")
    if operation == "add_weight" and parameters.get("unitKey", "kg") not in {"kg", "lbs"}:
        raise ValueError("Weight unit must be kg or lbs")
    if operation == "add_body_composition":
        for field, value in parameters.items():
            if field in {"timestamp", "weight"} or value is None: continue
            if isinstance(value,bool) or not isinstance(value,(int,float)) or value < 0:
                raise ValueError("Nonnegative body-composition values required")
            if field.startswith("percent_") and value > 100:
                raise ValueError("Percentages must be 0–100")
    if operation == "add_hydration":
        amount = parameters["value_in_ml"]
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not 0 < amount <= 10000:
            raise ValueError("Hydration must be 1–10000 ml")
        if "cdate" not in parameters:
            raise ValueError("Explicit hydration date required")
        date.fromisoformat(parameters["cdate"])
    if operation == "add_blood_pressure":
        for field, low, high in (("systolic",70,260),("diastolic",40,150),("pulse",20,250)):
            value = parameters.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value,int) or not low <= value <= high):
                raise ValueError("Measurement outside supported SDK range")
    if operation == "replace_strength_sets":
        sets = parameters["payload"].get("exerciseSets")
        if not isinstance(sets, list) or len(sets) > 500:
            raise ValueError("Provide the complete exerciseSets list, up to 500 sets")
    return parameters


def validate(operation, parameters, strength_original=None):
    from .write_contracts import check
    if operation == "schedule_workout" and isinstance(parameters, dict):
        validate_schedule(parameters)
    check(operation,parameters,strength_original=strength_original)
    try:
        result = _validate(operation,parameters)
    except WriteInputError as error:
        if error.operation != operation:raise WriteInputError(operation,str(error)) from None
        raise
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):
        raise WriteInputError(operation,"Invalid operation-specific content. Query get_garmin_write_schema and use a complete original template where required.") from None
    return result


def identifiers(raw):
    result = {}
    def walk(value):
        if isinstance(value, dict):
            for name, child in value.items():
                if name in {"workoutId", "activityId", "scheduledWorkoutId", "internalId", "id", "samplePk", "version", "messageId"} and isinstance(child, (str,int)) and not isinstance(child,bool):
                    result.setdefault(name, []).append(str(child))
                elif isinstance(child, (dict,list)):
                    walk(child)
        elif isinstance(value,list):
            for child in value[:100]: walk(child)
    walk(raw)
    return {name: values[:100] for name, values in result.items()}


@contextmanager
def prevent_sdk_replay(client):
    """SDK 0.3.17 replays a request after 401; never replay account mutations."""
    native=getattr(client,"client",None)
    session=getattr(native,"_api_session",None)
    if session is None:
        yield  # Intercepted/offline SDK transports do not have an API session.
        return
    class Session:
        sent=False
        def __getattr__(self,name): return getattr(session,name)
        def request(self,method,*args,**kwargs):
            if method.upper() in {"POST","PUT","PATCH","DELETE"}:
                if self.sent: raise RequestError("WRITE_REPLAY_BLOCKED")
                self.sent=True
            return session.request(method,*args,**kwargs)
    native._api_session=Session()
    try: yield
    finally: native._api_session=session


def invoke_write(client,method,*args,**kwargs):
    with prevent_sdk_replay(client):
        return getattr(client,method)(*args,**kwargs)


def preflight(client,operation,p):
    """Fixed reads establish existing targets and catalog tuples before mutation."""
    if operation in {"rename_workout","delete_workout"}:
        from .lifecycle import fingerprint
        original=client.get_workout_by_id(p["workout_id"])
        if not isinstance(original,dict) or original.get("workoutName")!=p["expected_name"] or fingerprint(original)!=p["expected_content_sha256"]:
            raise RequestError("WORKOUT_TARGET_CHANGED")
    if operation=="schedule_existing_workouts":
        for item in p["workouts"]:
            preflight(client,"schedule_workout",item)
    if operation in {"update_workout","schedule_workout","send_workout_to_device"}:
        if not isinstance(client.get_workout_by_id(p["workout_id"]),dict):
            raise RequestError("INVALID_PREFLIGHT_RESPONSE")
    if operation=="schedule_workout":
        day=date.fromisoformat(p["date_str"])
        raw=client.get_scheduled_workouts(day.year,day.month)
        if not isinstance(raw,dict): raise RequestError("INVALID_PREFLIGHT_RESPONSE")
        for row in raw.get("calendarItems",[]):
            if row.get("itemType")=="workout" and str(row.get("date","")).startswith(p["date_str"]) and any(
                    str(row.get(k))==str(p["workout_id"]) for k in ("workoutId","groupId")):
                raise RequestError("ALREADY_SCHEDULED")
    if operation=="unschedule_workout":
        if not isinstance(client.get_scheduled_workout_by_id(p["scheduled_workout_id"]),dict):
            raise RequestError("INVALID_PREFLIGHT_RESPONSE")
    if operation=="send_workout_to_device":
        rows=client.get_devices()
        if not isinstance(rows,list) or not any(str(v.get("deviceId"))==str(p["device_id"]) or
                str(v.get("userDeviceId"))==str(p["device_id"]) for v in rows):
            raise RequestError("DEVICE_NOT_FOUND")
    if operation in {"set_activity_name","set_activity_description","set_activity_type","replace_strength_sets"}:
        if not isinstance(client.get_activity(p["activity_id"]),dict):
            raise RequestError("INVALID_PREFLIGHT_RESPONSE")
    if operation=="replace_strength_sets":
        original=client.get_activity_exercise_sets(p["activity_id"])
        if not isinstance(original,dict) or not isinstance(original.get("exerciseSets"),list):
            raise RequestError("INVALID_PREFLIGHT_RESPONSE")
        for field in ("exerciseSetId","exerciseSetUUID"):
            known={str(v[field]) for v in original["exerciseSets"] if field in v}
            if any(field in v and str(v[field]) not in known for v in p["payload"]["exerciseSets"]):
                raise RequestError("EXERCISE_SET_TARGET_MISMATCH")
    if operation in {"set_activity_type","create_manual_activity"}:
        rows=client.get_activity_types()
        if not isinstance(rows,list): raise RequestError("INVALID_PREFLIGHT_RESPONSE")
        if operation=="set_activity_type":
            if not any(all(v.get(k)==p[field] for k,field in (
                    ("typeId","type_id"),("typeKey","type_key"),("parentTypeId","parent_type_id"))) for v in rows):
                raise RequestError("ACTIVITY_TYPE_MISMATCH")
        elif not any(v.get("typeKey")==p["type_key"] and manual_type_supported(v) for v in rows):
            raise RequestError("ACTIVITY_TYPE_MISMATCH")


COMMIT_TOOLS = {
    "rename_workout":"commit_garmin_workout_rename", "delete_workout":"commit_garmin_workout_delete",
    "schedule_existing_workouts":"commit_garmin_existing_workout_calendar",
    "create_workout": "commit_garmin_workout_creation",
    "update_workout": "commit_garmin_workout_update",
    "schedule_workout": "commit_garmin_workout_schedule",
    "create_training_calendar": "commit_garmin_training_calendar",
}


def review_context(operation, parameters, digest):
    """Public review fields identify immutable intent; they never replace stored parameters."""
    context = {"content_sha256": digest}
    if operation in {"create_workout", "update_workout"}:
        workout = parameters["workout_json"]
        context.update(workout_name=workout["workoutName"], sport=workout["sportType"]["sportTypeKey"])
        if operation == "update_workout": context["workout_id"] = str(parameters["workout_id"])
    elif operation == "schedule_workout":
        context.update(workout_id=str(parameters["workout_id"]), date_str=parameters["date_str"])
    elif operation == "create_training_calendar":
        context["workouts"] = [{"date": item["date"], "workout_name": item["workout"]["workoutName"],
            "sport": item["workout"]["sportType"]["sportTypeKey"]} for item in parameters["workouts"]]
    if operation in {"rename_workout","delete_workout"}:
        context.update(workout_id=str(parameters["workout_id"]),expected_name=parameters["expected_name"])
        if operation=="rename_workout": context["workout_name"]=parameters["workout_name"]
        else: context["confirm_calendar_removal"]=parameters["confirm_calendar_removal"]
    elif operation=="schedule_existing_workouts":
        context["workouts"]=[{"workout_id":str(v["workout_id"]),"date_str":v["date_str"]} for v in parameters["workouts"]]
    return context


class WriteService:
    def __init__(self, directory: Path | str | None = None, runner: Callable[...,Any] = bounded_request) -> None:
        self.directory = Path(directory or data_directory())
        self.store = TokenStore(self.directory / "write-journal")
        self.settings = TokenStore(self.directory / "write-settings")
        self.runner = runner

    def enabled(self) -> bool:
        return not self.settings.exists() or json.loads(self.settings.load()).get("enabled") is True

    def require_enabled(self,operation=None):
        if not self.enabled(): raise RequestError("WRITES_DISABLED")
        settings=json.loads(self.settings.load()) if self.settings.exists() else {}
        if operation is not None and "operations" in settings:
            allowed=settings["operations"]
            if not isinstance(allowed,list) or any(v not in OPERATIONS for v in allowed) or operation not in allowed:
                raise RequestError("WRITE_OPERATION_DENIED")

    def prepare(self, operation, parameters, idempotency_key, strength_original=None):
        self.require_enabled(operation)
        parameters = validate(operation, parameters, strength_original=strength_original)
        if not isinstance(idempotency_key,str) or not 8 <= len(idempotency_key) <= 128:
            raise ValueError("Use a stable 8–128 character idempotency key for this intent")
        digest = hashlib.sha256(json.dumps([operation,parameters],sort_keys=True).encode()).hexdigest()
        intent = hashlib.sha256(idempotency_key.encode()).hexdigest()
        with session_lock(self.store):
            state = json.loads(self.store.load()) if self.store.exists() else {}
            if intent in state:
                draft = state[intent]
                if draft["digest"] != digest: raise ValueError("Idempotency key already has different content")
            else:
                if len(state) >= 1000: raise RequestError("JOURNAL_FULL")
                draft = {"draft_id": secrets.token_urlsafe(24), "operation":operation,
                    "parameters":parameters,"digest":digest,"status":"prepared",
                    "expires_at":time.time()+1800,"steps":[],"result":None}
                state[intent] = draft
                if len(json.dumps(state)) > 16 * 1024 * 1024:
                    raise RequestError("JOURNAL_FULL")
                self.store.save(json.dumps(state))
            preview = dict(draft)
            preview.pop("digest")
            if operation in COMMIT_TOOLS:
                preview["commit_tool"] = COMMIT_TOOLS[operation]
                preview["commit_arguments"] = {"draft_id": draft["draft_id"],
                    **review_context(operation, draft["parameters"], draft["digest"])}
            preview["warning"] = "Review before commit. Updates and exercise sets replace existing content. Calendar plans are scheduled workouts, not Garmin Coach plans. Do not retry unknown outcomes."
            if operation == "upload_activity_file":
                content = base64.b64decode(parameters["content_base64"])
                preview["parameters"] = {"format":parameters["format"],"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest()}
            return preview

    def commit(self, draft_id):
        self.require_enabled()
        if not isinstance(draft_id,str) or not 20 <= len(draft_id) <= 80: raise ValueError("Invalid draft ID")
        self.require_enabled(self.status(draft_id)["operation"])
        # Never use the read service's retry/cache loop for mutations.
        try:
            return self.runner(self.directory,"mcp_commit_write",(draft_id,),{})
        except RequestError as error:
            if error.code in {"DRAFT_NOT_FOUND","DRAFT_EXPIRED","WRITES_DISABLED","AUTH_REQUIRED"}:
                raise
            raise RequestError("WRITE_OUTCOME_UNKNOWN") from error

    def commit_reviewed(self, draft_id, operation, context):
        self.require_enabled()
        if not isinstance(draft_id, str) or not 20 <= len(draft_id) <= 80:
            raise WriteInputError(operation, "Use the draft_id returned by preparation.")
        with session_lock(self.store):
            state = json.loads(self.store.load()) if self.store.exists() else {}
            draft = next((value for value in state.values() if value["draft_id"] == draft_id), None)
            if draft is None: raise RequestError("DRAFT_NOT_FOUND")
            if (draft["operation"] != operation or context != review_context(
                    draft["operation"], draft["parameters"], draft["digest"])):
                raise WriteInputError(operation, "Commit operation/review fields must exactly match prepared commit_arguments. No Garmin request was sent; re-read the preview rather than changing the approved intent.")
        # Draft payloads are immutable; the existing execution lock handles concurrent/repeated commits.
        return self.commit(draft_id)

    def status(self,draft_id):
        if not isinstance(draft_id,str) or not 20<=len(draft_id)<=80: raise ValueError("Invalid draft ID")
        with session_lock(self.store):
            state=json.loads(self.store.load()) if self.store.exists() else {}
            draft=next((v for v in state.values() if v["draft_id"]==draft_id),None)
            if draft is None: raise RequestError("DRAFT_NOT_FOUND")
            return {k:draft.get(k) for k in ("draft_id","operation","status","result","steps","error","verification")}


def execute(client, directory, draft_id):
    service = WriteService(directory)
    service.require_enabled()
    with session_lock(service.store):
        state = json.loads(service.store.load())
        draft = next((value for value in state.values() if value["draft_id"] == draft_id),None)
        if not draft: raise RequestError("DRAFT_NOT_FOUND")
        if draft["status"] != "prepared":
            return {"draft_id":draft_id,"status":draft["status"],"result":draft["result"],"steps":draft["steps"],
                    "error":draft.get("error"),"verification":draft.get("verification")}
        if draft["expires_at"] <= time.time(): raise RequestError("DRAFT_EXPIRED")
        operation=draft["operation"]
        service.require_enabled(operation)
        try:
            strength_original = (client.get_activity_exercise_sets(draft["parameters"]["activity_id"])
                                 if operation == "replace_strength_sets" else None)
            parameters=validate(operation,draft["parameters"],strength_original=strength_original)
            if operation in EXTENDED_OPERATIONS:
                from .extended_writes import preflight as extended_preflight
                extended_state = extended_preflight(client, operation, parameters)
            elif operation in LIFESTYLE_OPERATIONS:
                from .lifestyle_writes import preflight as lifestyle_preflight
                lifestyle_rows = lifestyle_preflight(client, operation, parameters)
            else:
                preflight(client,operation,parameters)
        except Exception as error:
            draft["status"]="rejected"
            draft["error"]={"code":"INVALID_WRITE_INPUT" if isinstance(error,WriteInputError) else error_code(error),
                "stage":"validation" if isinstance(error,WriteInputError) else "preflight",
                "garmin_mutation_sent":False,
                "guidance":"No Garmin mutation was attempted. Correct the input or resolve the read/preflight error before preparing a reviewed new intent."}
            service.store.save(json.dumps(state))
            return {
                "draft_id":draft_id,"status":draft["status"],"result":draft["result"],"steps":draft["steps"],"error":draft["error"],"verification":draft.get("verification")}
        draft["status"] = "in_progress"
        service.store.save(json.dumps(state))  # Persist before the first network mutation.
        try:
            if operation in EXTENDED_OPERATIONS:
                from .extended_writes import perform as perform_extended
                with prevent_sdk_replay(client):
                    result = perform_extended(client, operation, parameters, extended_state)
                raw = result
            elif operation in LIFESTYLE_OPERATIONS:
                from .lifestyle_writes import perform
                with prevent_sdk_replay(client):
                    result = perform(client, operation, parameters, lifestyle_rows)
                raw = result
            elif operation == "rename_workout":
                original=client.get_workout_by_id(parameters["workout_id"])
                from .lifecycle import fingerprint
                if fingerprint(original)!=parameters["expected_content_sha256"]:
                    raise RequestError("WORKOUT_TARGET_CHANGED")
                original["workoutName"]=parameters["workout_name"]
                raw=invoke_write(client,"update_workout",parameters["workout_id"],original)
                result={"workout_id":str(parameters["workout_id"]),"workout_name":parameters["workout_name"]}
            elif operation == "delete_workout":
                raw=invoke_write(client,"delete_workout",parameters["workout_id"])
                result={"workout_id":str(parameters["workout_id"]),"deleted":True}
            elif operation == "schedule_existing_workouts":
                for index,item in enumerate(parameters["workouts"]):
                    # Recheck duplicates immediately before each write. Any failure stops the batch.
                    preflight(client,"schedule_workout",item)
                    raw=invoke_write(client,"schedule_workout",item["workout_id"],item["date_str"])
                    draft["steps"].append({"index":index,"workout_id":str(item["workout_id"]),"scheduled_date":item["date_str"]})
                    service.store.save(json.dumps(state))
                result={"kind":"existing_scheduled_workouts","count":len(draft["steps"])}
            elif operation == "create_training_calendar":
                for index,item in enumerate(parameters["workouts"]):
                    raw = invoke_write(client,"upload_workout",item["workout"])
                    workout_id = raw["workoutId"]
                    draft["steps"].append({"index":index,"created_workout_id":str(workout_id)})
                    service.store.save(json.dumps(state))
                    invoke_write(client,"schedule_workout",workout_id,item["date"])
                    draft["steps"][-1]["scheduled_date"] = item["date"]
                    service.store.save(json.dumps(state))
                result = {"kind":"scheduled_workouts","count":len(draft["steps"])}
            elif operation == "upload_activity_file":
                with tempfile.TemporaryDirectory(dir=service.store.directory) as temporary:
                    path = Path(temporary) / ("activity."+parameters["format"])
                    path.write_bytes(base64.b64decode(parameters["content_base64"]))
                    raw = invoke_write(client,"upload_activity",str(path))
                result = identifiers(raw)
            else:
                raw = invoke_write(client,METHODS[operation],**parameters)
                result = identifiers(raw)
            draft["result"] = result
            if operation in {"upload_activity_file","add_body_composition"} and isinstance(raw,dict):
                report=raw.get("detailedImportResult",{})
                if isinstance(report,dict) and report.get("failures"):
                    raise RequestError("IMPORT_REJECTED_OR_PARTIAL")
            from .mutation_targets import verification_result
            draft["verification"] = verification_result(operation, result)
            draft["result"], draft["status"] = result,"completed"
        except Exception as error:
            draft["status"] = "unknown"
            draft["verification"] = {"state":"unknown","stored_value_readback":"not_confirmed"}
            draft["error"] = {"code": error_code(error),
                "guidance": "The write outcome is unconfirmed. Inspect Garmin before proceeding; do not retry with a new key."}
        service.store.save(json.dumps(state))
        return {"draft_id":draft_id,"status":draft["status"],"result":draft["result"],"steps":draft["steps"],
                "error":draft.get("error"),"verification":draft.get("verification")}


def main():
    parser = argparse.ArgumentParser(description="Enable or disable account-write tools locally")
    parser.add_argument("command", choices=["enable","disable","status"])
    parser.add_argument("--operations",nargs="*",choices=OPERATIONS,help="Restrict writes to exactly these operations (empty denies all)")
    args = parser.parse_args()
    service = WriteService()
    if args.command != "status":
        settings=json.loads(service.settings.load()) if service.settings.exists() else {}
        settings["enabled"]=args.command == "enable"
        if args.operations is not None: settings["operations"]=args.operations
        service.settings.save(json.dumps(settings))
    print("Account writes:", "enabled" if service.enabled() else "disabled")


if __name__ == "__main__": main()
