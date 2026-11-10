"""Connect-specific unit adapters, advisory quality checks and readback comparison."""
import math
import re


def pace_speeds(bounds, unit="pace_s_km"):
    """Connect pace.zone stores faster speed first (unlike SDK lower/upper labels)."""
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError(f"{unit} requires [faster, slower]")
    if unit == "pace_min_mile":
        if any(not isinstance(v, str) or not re.fullmatch(r"\d{1,2}:[0-5]\d", v) for v in bounds):
            raise ValueError("pace_min_mile requires two M:SS strings, e.g. ['9:15', '11:30']")
        seconds = [int(v.split(":")[0])*60 + int(v.split(":")[1]) for v in bounds]
        distance, minimum, maximum = 1609.344, 120, 3600
    else:
        seconds = bounds
        distance, minimum, maximum = (100, 20, 1200) if unit == "pace_s_100m" else (1000, 60, 3600)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           or not minimum <= v <= maximum for v in seconds):
        raise ValueError(f"{unit} bounds must be finite and between {minimum} and {maximum} seconds")
    if seconds[0] >= seconds[1]:
        raise ValueError(f"{unit} must be [faster, slower], with distinct ordered bounds")
    return [distance / v for v in seconds]


def quality_warnings(workout):
    """Advisory only: never silently rewrite a prescription or personal notes."""
    warnings = []
    def visit(steps, path):
        conditions = set()
        for index, step in enumerate(steps):
            here = f"{path}[{index}]"
            if step.get("type") == "RepeatGroupDTO":
                children = step.get("workoutSteps", [])
                conditions.update(visit(children, here + ".workoutSteps"))
                if step.get("numberOfIterations", 1) > 1 and not any(
                        s.get("stepType", {}).get("stepTypeKey") in {"rest", "recovery"} for s in children):
                    warnings.append(here + ": repeated work has no rest; confirm this is intentional.")
            else:
                condition = step.get("endCondition", {}).get("conditionTypeKey")
                conditions.add(condition)
                if condition == "distance" and re.search(r"\btime[- ]based\b", str(step.get("description") or ""), re.I):
                    warnings.append(here + ": time-based notes conflict with a distance end condition.")
        return conditions
    conditions = set()
    for index, segment in enumerate(workout.get("workoutSegments", [])):
        conditions.update(visit(segment.get("workoutSteps", []), f"workoutSegments[{index}].workoutSteps"))
    if "distance" in conditions and re.search(r"\btime[- ]based\b", str(workout.get("description") or ""), re.I):
        warnings.append("description: time-based notes may contradict executable distance steps; review the wording.")
    return warnings


# Compare executable intent, including omitted targets/rests. Ignore server-generated
# metadata, but preserve all fields that affect execution or the user's description.
WORKOUT_FIELDS = ("workoutName", "description", "sportType", "poolLength", "poolLengthUnit", "workoutSegments")
SEGMENT_FIELDS = ("segmentOrder", "sportType", "workoutSteps")
STEP_FIELDS = ("type", "stepOrder", "childStepId", "stepType", "endCondition", "endConditionValue", "targetType",
    "targetValueOne", "targetValueTwo", "zoneNumber", "secondaryTargetType", "secondaryTargetValueOne",
    "secondaryTargetValueTwo", "secondaryZoneNumber", "category", "exerciseName", "weightValue", "weightUnit",
    "numberOfIterations", "skipLastRestStep", "description", "strokeType", "equipmentType", "drillType", "workoutSteps")


def compare_workout(expected, actual):
    def project(value, fields):
        result = {}
        ignored = {"workoutId", "workoutSegmentId", "stepId", "ownerId", "author", "createdDate", "updatedDate"}
        # Include additional requested metadata/estimates and advanced execution
        # fields. A metadata-only change must never be silently skipped.
        for key in dict.fromkeys([*fields, *value]):
            if key in ignored:
                continue
            item = value.get(key)
            if key in {"workoutSegments", "workoutSteps"}:
                child_fields = SEGMENT_FIELDS if key == "workoutSegments" else STEP_FIELDS
                item = [project(child, child_fields) for child in item] if isinstance(item, list) else item
            elif isinstance(item, dict) and (key.endswith("Type") or key.endswith("Unit") or key == "endCondition"):
                # Enum display order/translations are not execution parameters.
                item = {k: v for k, v in item.items() if k.endswith("Key") or k.endswith("Id") or k == "factor"}
            if key == "skipLastRestStep":
                item = False if item is None else item
            if key == "description":
                item = item or ""
            result[key] = item
        return result
    differences = []
    def compare(left, right, path):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in left:
                compare(left[key], right.get(key), path + "." + key)
        elif isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
            for index, (a, b) in enumerate(zip(left, right)):
                compare(a, b, f"{path}[{index}]")
        elif isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)) and not isinstance(right, bool):
            if not math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-6):
                differences.append(path)
        elif left != right:
            differences.append(path)
    compare(project(expected, WORKOUT_FIELDS), project(actual, WORKOUT_FIELDS), "workout")
    if expected.get("workoutId") is not None and str(expected["workoutId"]) != str(actual.get("workoutId")):
        differences.append("workout.workoutId")
    return {"state": "verified" if not differences else "mismatch", "stored_value_readback": "matched" if not differences else "mismatched",
        "mismatch_paths": differences[:100], "mismatches_truncated": len(differences) > 100,
        "app_display_verified": False, "watch_execution_verified": False,
        "calendar_association_verified": False}
