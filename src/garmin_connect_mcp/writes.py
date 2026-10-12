"""Opt-in, previewed account writes with a durable at-most-once journal."""
import argparse
import base64
import hashlib
import inspect
import json
import math
import secrets
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from .auth import TokenStore, data_directory
from .runtime import RequestError, session_lock, bounded_request

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
OPERATIONS = tuple(METHODS) + ("create_training_calendar",)
WriteOperation = Literal["create_workout", "update_workout", "schedule_workout", "unschedule_workout",
    "send_workout_to_device", "create_manual_activity", "upload_activity_file", "set_activity_name",
    "set_activity_description", "set_activity_type", "replace_strength_sets", "add_weight",
    "add_body_composition", "add_hydration", "add_blood_pressure", "create_training_calendar"]
SPORTS = {"running", "cycling", "swimming", "walking", "hiking", "strength_training"}


def validate(operation, parameters):
    """Validate a fixed SDK operation; never accept endpoints or local file paths."""
    from garminconnect import Garmin
    if operation not in OPERATIONS or not isinstance(parameters, dict):
        raise ValueError("Unsupported operation")
    parameters = json.loads(json.dumps(parameters, allow_nan=False))
    if operation != "upload_activity_file" and len(json.dumps(parameters)) > 12000:
        raise ValueError("Preview payload exceeds 12 KiB")
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
        content = base64.b64decode(parameters["content_base64"], validate=True)
        if not content or len(content) > 2 * 1024 * 1024:
            raise ValueError("Activity file must be 1 byte–2 MiB")
        if parameters["format"] == "fit" and (len(content) < 12 or content[8:12] != b".FIT"):
            raise ValueError("Invalid FIT header")
        if parameters["format"] != "fit":
            from defusedxml import ElementTree
            root = ElementTree.fromstring(content)
            expected = "gpx" if parameters["format"] == "gpx" else "TrainingCenterDatabase"
            if root.tag.split("}")[-1] != expected:
                raise ValueError("Invalid activity XML format")
        return parameters
    method = METHODS[operation]
    inspect.signature(getattr(Garmin, method)).bind(None, **parameters)
    if operation in {"create_workout", "update_workout"}:
        payload = parameters["workout_json"]
        if not isinstance(payload, dict) or not isinstance(payload.get("workoutName"), str) or not payload["workoutName"].strip():
            raise ValueError("A named complete Garmin workout JSON template is required")
        if payload.get("sportType", {}).get("sportTypeKey") not in SPORTS:
            raise ValueError("Unsupported workout sport")
        segments = payload.get("workoutSegments")
        if not isinstance(segments, list) or not 1 <= len(segments) <= 20:
            raise ValueError("Provide 1–20 workout segments")
        for segment in segments:
            steps = segment.get("workoutSteps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
                raise ValueError("Provide 1–100 steps per segment")
    for name, value in parameters.items():
        if name.endswith("_id"):
            if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
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


def identifiers(raw):
    result = {}
    def walk(value):
        if isinstance(value, dict):
            for name, child in value.items():
                if name in {"workoutId", "activityId", "scheduledWorkoutId", "internalId", "id"} and isinstance(child, (str,int)):
                    result.setdefault(name, []).append(str(child))
                elif isinstance(child, (dict,list)):
                    walk(child)
        elif isinstance(value,list):
            for child in value[:100]: walk(child)
    walk(raw)
    return {name: values[:100] for name, values in result.items()}


class WriteService:
    def __init__(self, directory=None, runner=bounded_request):
        self.directory = Path(directory or data_directory())
        self.store = TokenStore(self.directory / "write-journal")
        self.settings = TokenStore(self.directory / "write-settings")
        self.runner = runner

    def enabled(self):
        return self.settings.exists() and json.loads(self.settings.load()).get("enabled") is True

    def require_enabled(self):
        if not self.enabled(): raise RequestError("WRITES_DISABLED")

    def prepare(self, operation, parameters, idempotency_key):
        self.require_enabled()
        parameters = validate(operation, parameters)
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
            preview["warning"] = "Review before commit. Updates and exercise sets replace existing content. Calendar plans are scheduled workouts, not Garmin Coach plans. Do not retry unknown outcomes."
            if operation == "upload_activity_file":
                content = base64.b64decode(parameters["content_base64"])
                preview["parameters"] = {"format":parameters["format"],"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest()}
            return preview

    def commit(self, draft_id):
        self.require_enabled()
        if not isinstance(draft_id,str) or not 20 <= len(draft_id) <= 80: raise ValueError("Invalid draft ID")
        # Never use the read service's retry/cache loop for mutations.
        try:
            return self.runner(self.directory,"mcp_commit_write",(draft_id,),{})
        except RequestError as error:
            if error.code in {"DRAFT_NOT_FOUND","DRAFT_EXPIRED","WRITES_DISABLED","AUTH_REQUIRED"}:
                raise
            raise RequestError("WRITE_OUTCOME_UNKNOWN") from error


def execute(client, directory, draft_id):
    service = WriteService(directory)
    service.require_enabled()
    with session_lock(service.store):
        state = json.loads(service.store.load())
        draft = next((value for value in state.values() if value["draft_id"] == draft_id),None)
        if not draft: raise RequestError("DRAFT_NOT_FOUND")
        if draft["status"] != "prepared":
            return {"draft_id":draft_id,"status":draft["status"],"result":draft["result"],"steps":draft["steps"]}
        if draft["expires_at"] <= time.time(): raise RequestError("DRAFT_EXPIRED")
        operation, parameters = draft["operation"], validate(draft["operation"],draft["parameters"])
        draft["status"] = "in_progress"
        service.store.save(json.dumps(state))  # Persist before the first network mutation.
        try:
            if operation == "create_training_calendar":
                for index,item in enumerate(parameters["workouts"]):
                    raw = client.upload_workout(item["workout"])
                    workout_id = raw["workoutId"]
                    draft["steps"].append({"index":index,"created_workout_id":str(workout_id)})
                    service.store.save(json.dumps(state))
                    client.schedule_workout(workout_id,item["date"])
                    draft["steps"][-1]["scheduled_date"] = item["date"]
                    service.store.save(json.dumps(state))
                result = {"kind":"scheduled_workouts","count":len(draft["steps"])}
            elif operation == "upload_activity_file":
                with tempfile.TemporaryDirectory(dir=service.store.directory) as temporary:
                    path = Path(temporary) / ("activity."+parameters["format"])
                    path.write_bytes(base64.b64decode(parameters["content_base64"]))
                    raw = client.upload_activity(str(path))
                result = identifiers(raw)
            else:
                raw = getattr(client,METHODS[operation])(**parameters)
                result = identifiers(raw)
            draft["result"], draft["status"] = result,"completed"
        except Exception:
            draft["status"] = "unknown"
        service.store.save(json.dumps(state))
        return {"draft_id":draft_id,"status":draft["status"],"result":draft["result"],"steps":draft["steps"]}


def main():
    parser = argparse.ArgumentParser(description="Enable or disable account-write tools locally")
    parser.add_argument("command", choices=["enable","disable","status"])
    args = parser.parse_args()
    service = WriteService()
    if args.command != "status":
        service.settings.save(json.dumps({"enabled":args.command == "enable"}))
    print("Account writes:", "enabled" if service.enabled() else "disabled")


if __name__ == "__main__": main()
