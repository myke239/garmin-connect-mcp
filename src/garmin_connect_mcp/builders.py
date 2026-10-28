"""High-level pure workout builders; every result passes the existing write validator."""
import copy
import math
from .sport_schemas import sport_enum, build_workout
from .workout_discovery import strength_step
from .workout_authoring import repeat, order_steps, duration_summary, resolve_strength
from .writes import WriteInputError


def integer(value, minimum, maximum, label):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(label + " is outside the supported whole-number range")
    return value


def step(order, duration=None, distance=None, step_type="interval"):
    if (duration is None) == (distance is None):
        raise ValueError("Choose one duration_seconds or distance_m")
    value = duration if duration is not None else distance
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 604800:
        raise ValueError("Duration/distance must be finite and positive")
    return {"type": "ExecutableStepDTO", "stepOrder": order,
        "stepType": {"stepTypeId": {"warmup": 1, "cooldown": 2, "interval": 3, "recovery": 4, "rest": 5, "main": 8}[step_type],
            "stepTypeKey": step_type},
        "endCondition": {"conditionTypeId": 2 if duration is not None else 3,
            "conditionTypeKey": "time" if duration is not None else "distance"},
        "endConditionValue": value,
        "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}}


def finish(sport, name, steps):
    count = order_steps(steps)
    if count > 100:
        raise WriteInputError("build_garmin_workout", "Workout exceeds the connector limit of 100 stored steps; split the session")
    result = build_workout(sport, name, workout_segments=[
        {"segmentOrder": 1, "sportType": sport_enum(sport), "workoutSteps": steps}])
    seconds, unknown = duration_summary(steps)
    result["workout_json"]["estimatedDurationInSecs"] = 0 if unknown else seconds
    result["duration_estimate"] = {"programmed_seconds": seconds,
        "untimed_executions": unknown, "total_seconds": None if unknown else seconds,
        "basis": "Programmed intervals only. Rep/distance/open steps have unknown duration; successful hold time and actual performance are not measured."}
    result["stored_step_count"] = count
    result["warnings"] = (["More than 50 stored steps: check this sport and device's limit or split the workout."] if count > 50 else [])
    result["watch_execution_verified"] = False
    result["guidance"] = "Pure draft. Prepare, approve, commit and read back. Watch execution requires physical sync verification."
    return result


def strength_workout(name, exercises, defaults=None):
    if not isinstance(exercises, list) or not 1 <= len(exercises) <= 30:
        raise WriteInputError("build_garmin_strength_workout", "exercises: provide 1-30 exercise specifications")
    defaults = {} if defaults is None else defaults
    try:
        if not isinstance(defaults, dict) or set(defaults) - {"rest_between_sets_seconds", "rest_between_exercises_seconds"}:
            raise ValueError("use rest_between_sets_seconds and rest_between_exercises_seconds")
        set_rest = integer(defaults.get("rest_between_sets_seconds", 60), 0, 3600, "rest_between_sets_seconds")
        transition = integer(defaults.get("rest_between_exercises_seconds", 120), 0, 3600, "rest_between_exercises_seconds")
    except ValueError as error:
        raise WriteInputError("build_garmin_strength_workout", f"defaults: {error}") from None
    steps = []
    warnings, preview = [], []
    allowed = {"name", "category", "exercise", "sets", "reps", "duration_seconds", "weight_kg", "rest_seconds", "notes", "include_final_rest", "transition_seconds"}
    for index, exercise in enumerate(exercises):
        try:
            if not isinstance(exercise, dict) or set(exercise) - allowed:
                raise ValueError("unknown strength fields; see the builder contract")
            timed = "duration_seconds" in exercise
            if timed == ("reps" in exercise):
                raise ValueError("provide exactly one reps or duration_seconds")
            count = integer(exercise.get("sets", 1), 1, 99, "sets")
            include_final = exercise.get("include_final_rest", False)
            if not isinstance(include_final, bool):
                raise ValueError("include_final_rest must be boolean")
            match, label = resolve_strength(exercise)
            if match is None:
                template = step(1, duration=exercise["duration_seconds"])
                warnings.append(f"exercises[{index}]: no exact catalog match; Garmin may display a generic exercise label. The actual movement is preserved in description.")
            else:
                template = strength_step(match["category"], match["exercise"],
                    1 if timed else exercise["reps"], 1, exercise.get("weight_kg"))["step"]
            if timed:
                template["endCondition"] = {"conditionTypeId": 2, "conditionTypeKey": "time"}
                template["endConditionValue"] = integer(exercise["duration_seconds"], 1, 86400, "duration_seconds")
            notes = exercise.get("notes", "")
            if not isinstance(notes, str) or len(notes) > 500:
                raise ValueError("notes must be at most 500 characters")
            template["description"] = label + (" — " + notes if notes else "")
            rest = integer(exercise.get("rest_seconds", set_rest), 0, 3600, "rest_seconds")
            gap = integer(exercise.get("transition_seconds", transition), 0, 3600, "transition_seconds")
            if not rest and include_final:
                raise ValueError("include_final_rest requires positive rest_seconds")
            children = [template]
            if rest:
                children.append(step(1, duration=rest, step_type="rest"))
            steps.append(repeat(children, count, include_final))
            # The final intra-exercise rest is skipped unless explicitly prescribed.
            # An intentional final recovery belongs to its block, before transition.
            gap = gap if index < len(exercises) - 1 else 0
            if gap:
                transition_step = step(1, duration=gap, step_type="rest")
                transition_step["description"] = "Equipment transition"
                steps.append(transition_step)
            preview.append({"name": label, "sets": count,
                "duration_seconds" if timed else "reps": template["endConditionValue"],
                "rest_seconds": rest, "include_final_rest": include_final,
                "transition_seconds": gap, "catalog_resolved": match is not None})
        except ValueError as error:
            raise WriteInputError("build_garmin_strength_workout", f"exercises[{index}]: {error}") from None
    result = finish("strength_training", name, steps)
    result["warnings"].extend(warnings)
    result["preview"] = preview
    return result


def running_workout(name, intervals, warmup_seconds=0, cooldown_seconds=0):
    if not isinstance(intervals, list) or not 1 <= len(intervals) <= 30:
        raise ValueError("Provide 1-30 interval specifications")
    steps = []
    for value, kind in ((warmup_seconds, "warmup"),):
        integer(value, 0, 86400, kind)
        if value:
            steps.append(step(1, duration=value, step_type=kind))
    for interval in intervals:
        if not isinstance(interval, dict) or set(interval) - {"duration_seconds", "distance_m", "repeats", "recovery_seconds", "hr_zone", "pace_s_km", "include_final_recovery"}:
            raise ValueError("Unknown running fields")
        template = step(1, interval.get("duration_seconds"), interval.get("distance_m"))
        if "hr_zone" in interval and "pace_s_km" in interval:
            raise ValueError("Choose either hr_zone or pace_s_km")
        if "hr_zone" in interval:
            template["targetType"] = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"}
            template["zoneNumber"] = integer(interval["hr_zone"], 1, 5, "hr_zone")
        if "pace_s_km" in interval:
            bounds = interval["pace_s_km"]
            if not isinstance(bounds, list) or len(bounds) != 2 or any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not 60 <= v <= 3600 for v in bounds):
                raise ValueError("pace_s_km needs two finite bounds, 60-3600 seconds/km")
            if bounds[0] >= bounds[1]:
                raise ValueError("pace_s_km must be [faster, slower]")
            template["targetType"] = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}
            template["targetValueOne"], template["targetValueTwo"] = [1000 / v for v in reversed(bounds)]
        count = integer(interval.get("repeats", 1), 1, 99, "repeats")
        recovery = integer(interval.get("recovery_seconds", 0), 0, 3600, "recovery_seconds")
        include_final = interval.get("include_final_recovery", False)
        if not isinstance(include_final, bool) or (include_final and not recovery):
            raise ValueError("include_final_recovery must be boolean and requires recovery_seconds")
        children = [template]
        if recovery and (count > 1 or include_final):
            children.append(step(1, duration=recovery, step_type="recovery"))
        if count > 1:
            steps.append(repeat(children, count, include_final))
        else:
            steps.extend(children)
    integer(cooldown_seconds, 0, 86400, "cooldown_seconds")
    if cooldown_seconds:
        steps.append(step(1, duration=cooldown_seconds, step_type="cooldown"))
    return finish("running", name, steps)


def swim_workout(name, pool_length_m, intervals):
    if pool_length_m not in (25, 50):
        raise ValueError("Only 25m and 50m pools are currently supported for this builder")
    if not isinstance(intervals, list) or not 1 <= len(intervals) <= 30:
        raise ValueError("Provide 1-30 swim intervals")
    strokes = {"any_stroke": 1, "backstroke": 2, "breaststroke": 3, "fly": 5, "free": 6}
    equipment = {"fins": 1, "kickboard": 2, "paddles": 3, "pull_buoy": 4, "snorkel": 5}
    drills = {"kick": 1, "pull": 2, "drill": 3}
    steps = []
    for interval in intervals:
        if set(interval) - {"distance_m", "stroke", "equipment", "drill", "repeats", "rest_seconds", "pace_s_100m"}:
            raise ValueError("Unknown swim fields")
        distance = integer(interval["distance_m"], pool_length_m, 10000, "distance_m")
        if distance % pool_length_m:
            raise ValueError("Swim distance must be a whole number of pool lengths")
        template = step(1, distance=distance, step_type="main")
        stroke = interval.get("stroke", "any_stroke")
        if stroke not in strokes:
            raise ValueError("Unknown stroke")
        template["strokeType"] = {"strokeTypeId": strokes[stroke], "strokeTypeKey": stroke, "displayOrder": strokes[stroke]}
        for field, mapping, prefix in (("equipment", equipment, "equipment"), ("drill", drills, "drill")):
            if field in interval:
                value = interval[field]
                if value not in mapping:
                    raise ValueError("Unknown " + field)
                template[prefix + "Type"] = {prefix + "TypeId": mapping[value], prefix + "TypeKey": value, "displayOrder": mapping[value]}
        if "pace_s_100m" in interval:
            bounds = interval["pace_s_100m"]
            if not isinstance(bounds, list) or len(bounds) != 2 or any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not 20 <= v <= 1200 for v in bounds) or bounds[0] >= bounds[1]:
                raise ValueError("pace_s_100m needs [faster,slower], 20-1200 seconds/100m")
            template["targetType"] = {"workoutTargetTypeId":6,"workoutTargetTypeKey":"pace.zone"}
            template["targetValueOne"], template["targetValueTwo"] = [100 / v for v in reversed(bounds)]
        rest = integer(interval.get("rest_seconds", 0), 0, 3600, "rest_seconds")
        count = integer(interval.get("repeats", 1), 1, 30, "repeats")
        for index in range(count):
            steps.append(copy.deepcopy(template))
            if rest and index < count - 1:
                rest_step = step(1, duration=rest, step_type="rest")
                rest_step["endCondition"] = {"conditionTypeId":8,"conditionTypeKey":"fixed.rest"}
                steps.append(rest_step)
    result = finish("swimming", name, steps)
    result["workout_json"].update(poolLength=pool_length_m, poolLengthUnit={"unitKey": "meter"})
    from .writes import validate
    validate("create_workout", {"workout_json": result["workout_json"]})
    return result
