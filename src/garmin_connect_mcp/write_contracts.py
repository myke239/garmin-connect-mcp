"""Account-write contracts shared by validation, tools and agent discovery."""
import copy
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jsonschema import Draft202012Validator,validators
STRICT = validators.extend(Draft202012Validator,type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
    "integer",lambda checker,value:isinstance(value,int) and not isinstance(value,bool)))

ID = {"oneOf": [{"type":"integer", "minimum":1, "maximum":9007199254740991},
                {"type":"string", "pattern":"^[1-9][0-9]{0,19}$"}]}
DATE = {"type":"string", "pattern":"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}
STAMP = {"type":"string", "minLength":20, "maxLength":40,
         "description":"ISO 8601 timestamp with explicit offset; actual measurement time"}
TEXT = {"type":"string", "maxLength":2000}
NAME = {"type":"string", "minLength":1, "maxLength":200}
NUMBER = {"type":"number", "minimum":0}
WORKOUT = {"type":"object", "required":["workoutName","sportType","workoutSegments"],
    "properties":{"workoutName":NAME,"sportType":{"type":"object"},
                  "workoutSegments":{"type":"array","minItems":1,"maxItems":20,"items":{"type":"object"}}}}


def obj(properties, required=None):
    return {"type":"object", "properties":properties,
            "required":list(properties) if required is None else required, "additionalProperties":False}


COMPOSITION = {
    "weight":{"type":"number", "exclusiveMinimum":0, "maximum":655.34, "description":"kg; FIT uint16 scaled by 100"},
    "percent_fat":{"type":"number", "minimum":0, "maximum":100},
    "percent_hydration":{"type":"number", "minimum":0, "maximum":100},
    **{k:{"type":"number", "minimum":0, "maximum":655.34, "description":"kg"}
       for k in ("visceral_fat_mass","bone_mass","muscle_mass")},
    **{k:{"type":"number", "minimum":0, "maximum":16383.5, "description":"kcal/day; FIT scale 4"}
       for k in ("basal_met","active_met")},
    **{k:{"type":"integer", "minimum":0, "maximum":254}
       for k in ("physique_rating","metabolic_age","visceral_fat_rating")},
    "bmi":{"type":"number", "minimum":0, "maximum":6553.4},
}

SCHEMAS = {
    "create_workout":obj({"workout_json":WORKOUT}),
    "update_workout":obj({"workout_id":ID,"workout_json":WORKOUT}),
    "schedule_workout":obj({"workout_id":ID,"date_str":DATE}),
    "unschedule_workout":obj({"scheduled_workout_id":ID}),
    "send_workout_to_device":obj({"workout_id":ID,"device_id":ID}),
    "create_training_calendar":obj({"workouts":{"type":"array","minItems":1,"maxItems":20,
        "items":obj({"date":DATE,"workout":WORKOUT})}}),
    "create_manual_activity":obj({"start_datetime":{"type":"string","maxLength":32},
        "time_zone":{"type":"string","minLength":1,"maxLength":100},"type_key":NAME,
        "distance_km":{"type":"number","minimum":0,"maximum":1000},
        "duration_min":{"type":"integer","minimum":1,"maximum":10080},"activity_name":NAME}),
    "upload_activity_file":obj({"format":{"enum":["fit","tcx","gpx"]},
        "content_base64":{"type":"string","minLength":1,"maxLength":2796204}}),
    "set_activity_name":obj({"activity_id":ID,"title":NAME}),
    "set_activity_description":obj({"activity_id":ID,"description":TEXT}),
    "set_activity_type":obj({"activity_id":ID,"type_id":{"type":"integer","minimum":1},
        "type_key":NAME,"parent_type_id":{"type":"integer","minimum":0}}),
    "replace_strength_sets":obj({"activity_id":ID,"payload":{"type":"object",
        "required":["exerciseSets"],"properties":{"exerciseSets":{"type":"array","maxItems":500,
            "items":{"type":"object"}}}}}),
    "add_weight":obj({"weight":{"type":"number","exclusiveMinimum":0,"maximum":1000},
        "timestamp":STAMP,"unitKey":{"enum":["kg","lbs"]}},["weight","timestamp"]),
    "add_body_composition":obj({"timestamp":STAMP,**{k:{"anyOf":[v,{"type":"null"}]} for k,v in COMPOSITION.items()}},
        ["weight","timestamp"]),
    "add_hydration":obj({"value_in_ml":{"type":"number","exclusiveMinimum":0,"maximum":10000},
        "timestamp":STAMP,"cdate":DATE}),
    "add_blood_pressure":obj({"systolic":{"type":"integer","minimum":70,"maximum":260},
        "diastolic":{"type":"integer","minimum":40,"maximum":150},
        "pulse":{"anyOf":[{"type":"integer","minimum":20,"maximum":250},{"type":"null"}]},
        "timestamp":STAMP,"notes":TEXT},["systolic","diastolic","timestamp"]),
}

GUIDANCE = {
    "create_workout":"Read list_garmin_workout_sports and get_garmin_workout_schema for exact sport enums/complete examples; build_garmin_workout validates JSON without writing. Use find_garmin_exercises and build_garmin_strength_step for strength; resolve equipment variants explicitly and never substitute missing exercises. For yoga poses discover find_garmin_exercises(category=POSE), build_garmin_yoga_step for exact timed steps, then build_garmin_workout with explicit yoga segments. Complete SDK workout JSON. IDs accompany enum keys; seconds/metres in step.endConditionValue. Never invent pace-target units.",
    "update_workout":"Read original template first. Complete replacement preserves all untouched fields and matching workoutId.",
    "schedule_workout":"Use workout_id/date_str, not workoutId/date. Read calendar first to avoid duplicate schedules; verify after commit.",
    "unschedule_workout":"Use calendar entry ID from list_scheduled_workouts, not workout template ID. This removes one scheduled entry.",
    "send_workout_to_device":"Choose an explicit ID from list_garmin_devices. Completed means queued, not downloaded by the physical device.",
    "create_training_calendar":"Creates a template per entry, then schedules it. Not atomic; stop on partial/unknown and preserve returned IDs.",
    "create_manual_activity":"Use get_garmin_activity_schema for the exact live type and build_garmin_manual_activity to validate. Completed actual session only, not a planned calendar entry. Local start time with no offset plus IANA timezone. Resolve ambiguous/nonexistent daylight-saving times first. km and whole minutes. Private activity.",
    "upload_activity_file":"User-supplied activity file only; base64 bytes, never local paths. Max 2 MiB. Header/structure validation does not prove Garmin will accept it. GPS may be included.",
    "set_activity_name":"Verify activity ID and old name before edit. Changes name only; re-read after commit.",
    "set_activity_description":"Verify activity ID before edit. Empty description explicitly clears it.",
    "set_activity_type":"Read list_garmin_activity_types; supply a matching typeId/typeKey/parentTypeId tuple, never guess IDs.",
    "replace_strength_sets":"Read get_activity_edit_template first; pass complete exerciseSets body, preserving IDs and timestamps. Raw Garmin weight units are unverified; do not convert or invent. Empty list clears all sets.",
    "add_weight":"Record actual user-provided measurement, explicit time and kg/lbs. Never infer weight from activities.",
    "add_body_composition":"Actual measurements only. Weight/mass kg, percentages 0–100, energy kcal/day. Omit unmeasured fields; FIT representability limits are not medical limits.",
    "add_hydration":"Actual positive ml consumed; timestamp local date must match cdate. No subtract/overwrite through this operation.",
    "add_blood_pressure":"Actual measured systolic/diastolic mmHg; optional pulse bpm. No invented defaults, timestamps mandatory.",
}


def contract(operation):
    if operation not in SCHEMAS:
        raise ValueError("Unsupported write operation")
    return {"operation":operation,"parameter_schema":copy.deepcopy(SCHEMAS[operation]),
        "guidance":GUIDANCE[operation],"workflow":"Read evidence; prepare; review exact preview; use returned commit_tool/commit_arguments unchanged for workout operations (generic commit for other operations), only with authorization; verify. Never retry unknown/in_progress with a new key.",
        "validation_only":True,"garmin_request_sent":False}


def check(operation, parameters):
    """Return fixed guidance rather than jsonschema errors that echo private values."""
    from .writes import WriteInputError
    if operation not in SCHEMAS or not isinstance(parameters, dict):
        raise WriteInputError(operation if operation in SCHEMAS else "unsupported", "Choose a supported operation and an object of parameters; query get_garmin_write_schema.")
    try:
        json.dumps(parameters,allow_nan=False)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise WriteInputError(operation,"Parameters must be finite JSON values.") from None
    errors = list(STRICT(SCHEMAS[operation]).iter_errors(parameters))
    if errors:
        # Paths contain only known schema property names or integer indices.
        path = ".".join(str(v) for v in errors[0].absolute_path)
        safe_path = path if all(str(v).isdigit() or str(v) in SCHEMAS[operation]["properties"]
                                or str(v) in {"date","workout","weight"} for v in errors[0].absolute_path) else "parameters"
        raise WriteInputError(operation,"Invalid " + (safe_path or "parameters") + "; check required names, types and bounds in get_garmin_write_schema.")
    for field in ("timestamp","start_datetime"):
        if field in parameters:
            try:
                parsed = datetime.fromisoformat(parameters[field])
                if field == "timestamp" and (parsed.tzinfo is None or "T" not in parameters[field]):
                    raise ValueError
                if field == "start_datetime" and (parsed.tzinfo is not None or "T" not in parameters[field]):
                    raise ValueError
            except (ValueError,TypeError,OverflowError):
                raise WriteInputError(operation,field + " must be ISO 8601 with an offset for measurements and no offset for local manual activities.") from None
    dates = [parameters[k] for k in ("date_str","cdate") if k in parameters]
    if operation == "create_training_calendar": dates += [v["date"] for v in parameters["workouts"]]
    for value in dates:
        try:
            if date.fromisoformat(value).isoformat() != value: raise ValueError
        except ValueError:
            raise WriteInputError(operation,"Use a real calendar date in YYYY-MM-DD format.") from None
    if operation == "add_hydration" and datetime.fromisoformat(parameters["timestamp"]).date().isoformat() != parameters["cdate"]:
        raise WriteInputError(operation,"timestamp's local calendar date must match cdate.")
    if operation == "add_body_composition" and parameters["weight"] is None:
        raise WriteInputError(operation,"weight is required and cannot be null.")
    if operation == "update_workout" and "workoutId" in parameters["workout_json"] and str(parameters["workout_json"]["workoutId"]) != str(parameters["workout_id"]):
        raise WriteInputError(operation,"workoutId in the replacement body must match workout_id; do not target a copied template accidentally.")
    if operation == "create_workout" and parameters["workout_json"].get("workoutId") is not None:
        raise WriteInputError(operation,"Remove the source workoutId before creating a new template.")
    if operation == "create_training_calendar":
        seen=set()
        for item in parameters["workouts"]:
            if item["workout"].get("workoutId") is not None:
                raise WriteInputError(operation,"New calendar templates must not carry a source workoutId.")
            value=json.dumps(item,sort_keys=True)
            if value in seen: raise WriteInputError(operation,"The calendar batch contains duplicate date/template entries.")
            seen.add(value)
    if operation == "replace_strength_sets":
        if "activityId" in parameters["payload"] and str(parameters["payload"]["activityId"]) != str(parameters["activity_id"]):
            raise WriteInputError(operation,"activityId in the complete exercise payload must match activity_id.")
        from garminconnect.exercises import CATEGORIES,EXERCISES
        known={(v["category"],v["exercise"]) for v in EXERCISES}
        for row in parameters["payload"]["exerciseSets"]:
            for field in ("duration","weight","repetitionCount"):
                value=row.get(field)
                if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or value<0):
                    raise WriteInputError(operation,"Strength duration/weight/repetitions require nonnegative numeric raw values.")
            if row.get("repetitionCount") is not None and (not isinstance(row["repetitionCount"],int) or isinstance(row["repetitionCount"],bool)):
                raise WriteInputError(operation,"Strength repetitionCount must be an integer.")
            exercises=row.get("exercises",[])
            if not isinstance(exercises,list) or len(exercises)>10:
                raise WriteInputError(operation,"Each set supports at most 10 exercise objects.")
            for exercise in exercises:
                if not isinstance(exercise,dict) or exercise.get("category") not in CATEGORIES:
                    raise WriteInputError(operation,"Use valid categories from find_garmin_exercises; do not invent exercise labels.")
                if exercise.get("name") and (exercise["category"],exercise["name"]) not in known:
                    raise WriteInputError(operation,"Exercise name must match its Garmin category; use null for a known parent-only exercise.")
    if operation == "add_blood_pressure" and parameters["systolic"] <= parameters["diastolic"]:
        raise WriteInputError(operation,"Systolic must exceed diastolic; confirm the actual measurement.")
    if operation == "create_manual_activity":
        try: zone = ZoneInfo(parameters["time_zone"])
        except (ZoneInfoNotFoundError,ValueError):
            raise WriteInputError(operation,"time_zone must be an installed IANA timezone name.") from None
        local = datetime.fromisoformat(parameters["start_datetime"])
        for fold in (0,1):
            aware=local.replace(tzinfo=zone,fold=fold)
            from datetime import timezone
            if aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != local:
                raise WriteInputError(operation,"Local start time falls in a daylight-saving gap; choose a valid time.")
        if local.replace(tzinfo=zone,fold=0).utcoffset() != local.replace(tzinfo=zone,fold=1).utcoffset():
            raise WriteInputError(operation,"Local start time is ambiguous during daylight-saving fallback; this SDK cannot express a fold. Choose an unambiguous time.")
    if operation == "add_body_composition":
        from datetime import timezone
        value=datetime.fromisoformat(parameters["timestamp"]).astimezone(timezone.utc).timestamp()-631065600
        if not 0<=value<4294967295:
            raise WriteInputError(operation,"Composition timestamp must be representable by the FIT epoch (1989-12-31 through the uint32 limit).")
