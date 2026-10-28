"""Pure structured-workout helpers; no account access or inferred exercise aliases."""
from garminconnect.workout import ExecutableStep, create_repeat_group


def repeat(steps, count, include_final_rest=False):
    group = create_repeat_group(count, [ExecutableStep(**row) for row in steps], 1)
    result = group.model_dump(mode="json", exclude_none=True)
    # 0.3.17 permits extra DTO fields; newer upstream versions expose this field.
    result["skipLastRestStep"] = not include_final_rest and steps[-1]["stepType"]["stepTypeKey"] in {"rest", "recovery"}
    return result


def order_steps(steps):
    """Assign global preorder positions and shared repeat/child grouping IDs."""
    order = 0

    def visit(items, group_id=None):
        nonlocal order
        for item in items:
            order += 1
            item["stepOrder"] = order
            if item["type"] == "RepeatGroupDTO":
                item["childStepId"] = order
                visit(item["workoutSteps"], order)
            elif group_id is not None:
                item["childStepId"] = group_id
    visit(steps)
    return order


def duration_summary(steps):
    """Count prescribed time; never equate rep/distance/hold goals with performance."""
    seconds, unknown = 0, 0
    for item in steps:
        if item["type"] == "RepeatGroupDTO":
            timed, untimed = duration_summary(item["workoutSteps"])
            count = item["numberOfIterations"]
            seconds += timed * count
            unknown += untimed * count
            if item.get("skipLastRestStep"):
                last_timed, last_unknown = duration_summary(item["workoutSteps"][-1:])
                seconds -= last_timed
                unknown -= last_unknown
        elif item["endCondition"]["conditionTypeKey"] == "time":
            seconds += item["endConditionValue"]
        else:
            unknown += 1
    return seconds, unknown


def resolve_strength(exercise):
    from garminconnect.exercises import EXERCISES
    from .workout_discovery import exercises, normalize

    category, identifier = exercise.get("category"), exercise.get("exercise")
    name = exercise.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 100):
        raise ValueError("name must contain 1-100 characters")
    if category is not None or identifier is not None:
        match = next((row for row in EXERCISES if row["category"] == category and row["exercise"] == identifier), None)
        if match is None:
            raise ValueError("category/exercise must be an exact pair from find_garmin_exercises")
        # An explicit pair is a conscious catalog selection; the optional name is a label.
        return match, name or match["name"]
    if name is None:
        raise ValueError("provide name or an exact category/exercise pair")
    found = exercises(name)
    matches = [row for row in found["exact_matches"] if row["category"] != "POSE"]
    # Bare enum names may be reused across equipment categories (e.g. SQUAT).
    # A unique exact display name is a stronger match than an enum-only match.
    display_matches = [row for row in matches if normalize(row["name"]) == normalize(name)]
    matches = display_matches or matches
    if len(matches) == 1:
        match = matches[0]
        return match, name
    if len(matches) > 1:
        raise ValueError("name is ambiguous; use find_garmin_exercises and select category/exercise")
    if "duration_seconds" not in exercise:
        raise ValueError("name has no exact match; use find_garmin_exercises and select category/exercise; never substitute a related movement")
    if "weight_kg" in exercise:
        raise ValueError("generic timed steps do not encode weight_kg; resolve a catalog pair first")
    return None, name
