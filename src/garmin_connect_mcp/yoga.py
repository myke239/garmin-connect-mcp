"""Pinned Garmin pose identifiers verified through SDK upload/readback."""
import json
from importlib.resources import files

CATALOG = json.loads(files("garmin_connect_mcp").joinpath("yoga_poses.json").read_text(encoding="utf-8"))
POSES = frozenset(row["exerciseName"] for row in CATALOG["poses"])


def pose_step(exercise, duration_seconds, step_order):
    from .writes import WriteInputError
    from .sport_schemas import sport_enum
    from garminconnect.workout import create_interval_step
    if not isinstance(exercise, str) or exercise not in POSES:
        raise WriteInputError("build_garmin_yoga_step", "Select an exact POSE exercise from find_garmin_exercises(category=POSE); never guess or substitute a pose.")
    for name, value, maximum in (("duration_seconds", duration_seconds, 86400), ("step_order", step_order, 100)):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise WriteInputError("build_garmin_yoga_step", name + " must be a positive whole number within the published bound.")
    step = create_interval_step(duration_seconds, step_order).model_dump(mode="json", exclude_none=True)
    step.update(category="POSE", exerciseName=exercise)
    return {"step": step, "sportType": sport_enum("yoga"), "garmin_request_sent": False,
        "guidance": "Assemble the selected ordered poses into yoga workoutSegments; build_garmin_workout validates JSON. Prepare, review/authorize, commit and read back. Schedule with workout_id and date_str. No watch animation or device compatibility claim."}
