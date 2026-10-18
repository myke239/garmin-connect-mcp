"""Offline read-to-write registry. Evidence is distinct from runtime permission."""
from dataclasses import dataclass

from .runtime import RequestError


@dataclass(frozen=True)
class Resource:
    name: str
    reads: tuple[str, ...]
    operations: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    target: str | None = None
    boundary: str = ""
    planned: tuple[str, ...] = ()
    local: bool = False


RESOURCES = (
    Resource("sleep", ("get_garmin_recovery", "get_garmin_coaching_day", "get_session_with_context", "get_garmin_sleep_mutation_target"),
             ("add_sleep", "update_sleep_times", "set_sleep_note", "clear_sleep_note"),
             fields=("start_time", "end_time", "note"), target="get_garmin_sleep_mutation_target",
             boundary="Native contract observed; real-night write acceptance not tested. No stage/score inputs or main sleep deletion.",
             planned=()),
    Resource("naps", ("get_garmin_recovery", "get_garmin_nap_mutation_target"), ("add_nap", "update_nap", "delete_nap"), target="get_garmin_nap_mutation_target", fields=("start_time", "end_time"),
             boundary="Native contracts observed; current-day eligibility and identity must be enforced.",
             planned=()),
    Resource("activities", ("list_activities", "get_activity", "get_activity_edit_template", "get_garmin_record_mutation_target"),
             ("create_manual_activity", "upload_activity_file", "set_activity_name", "set_activity_description", "set_activity_type", "delete_activity"),
             ("name", "description", "activity_type"), "get_activity_edit_template",
             "Recorded sample timelines are not arbitrary editable summary fields.", ("update_activity_summary",)),
    Resource("strength_sets", ("get_strength_sets", "get_activity_edit_template"), ("replace_strength_sets",),
             ("exercise_sets",), "get_activity_edit_template", "Complete replacement; recorded load units remain Garmin raw/unverified."),
    Resource("workouts", ("get_workout_template", "list_workout_templates", "clone_garmin_workout", "get_garmin_workout_mutation_target"),
             ("create_workout", "update_workout", "rename_workout", "delete_workout"),
             ("name", "description", "segments"), "get_garmin_workout_mutation_target"),
    Resource("calendar", ("list_scheduled_workouts",),
             ("schedule_workout", "unschedule_workout", "create_training_calendar", "schedule_existing_workouts"),
             ("workout_id", "date"), "list_scheduled_workouts", "Batch/move operations are not atomic."),
    Resource("devices", ("list_garmin_devices",), ("send_workout_to_device",),
             ("workout_queue",), "list_garmin_devices", "Queue acceptance does not prove physical sync; device settings need separate contracts."),
    Resource("weight", ("get_garmin_measurements", "get_garmin_record_mutation_target"), ("add_weight", "delete_weight_measurement"), ("weight", "timestamp"),
             "get_garmin_measurements", "Read and input units can differ.", ()),
    Resource("body_composition", ("get_garmin_measurements", "get_garmin_record_mutation_target"), ("add_body_composition",),
             ("actual_measurements",), "get_garmin_measurements", "FIT import may be asynchronous; no silent delete/recreate."),
    Resource("blood_pressure", ("get_garmin_measurements", "get_garmin_record_mutation_target"), ("add_blood_pressure", "delete_blood_pressure_measurement"),
             ("systolic", "diastolic", "pulse", "timestamp"), "get_garmin_measurements",
             "Actual measurements only.", ()),
    Resource("hydration", ("get_garmin_measurements", "get_garmin_record_mutation_target"), ("add_hydration", "adjust_hydration"), ("ml", "timestamp"),
             "get_garmin_measurements", "add_hydration adds positive ml; adjust_hydration accepts bounded signed corrections with fresh total guard.", ()),
    Resource("lifestyle", ("list_garmin_lifestyle_fields", "get_garmin_lifestyle_entries", "get_garmin_lifestyle_mutation_target"),
             ("create_lifestyle_behaviours", "rename_lifestyle_behaviour", "delete_lifestyle_behaviours",
              "set_lifestyle_log", "clear_lifestyle_log", "set_tracked_lifestyle_behaviours"),
             ("custom_name", "positive_integer_amount", "yes_no", "tracking"), "get_garmin_lifestyle_mutation_target",
             "Deleting definitions may remove history; zero writes are rejected, read zeros preserved."),
    Resource("lifestyle_auto_logging", ("get_garmin_lifestyle_auto_logging",), ("set_lifestyle_auto_logging",),
             ("enabled",), "get_garmin_lifestyle_auto_logging", "Setter is not live-verified; unset/null reset is unavailable."),
    Resource("heart_rate_zones", ("get_garmin_recovery",), boundary="Historical metrics differ from device-specific editable settings.", planned=("update_heart_rate_zones",)),
    Resource("personal_records", ("get_garmin_recovery",), boundary="Native mutation routes observed; accept/discard/assign semantics need verification."),
    Resource("training_status", ("get_garmin_recovery", "get_session_with_context"), boundary="Pause/resume is a setting, not an arbitrary status/load setter.", planned=("set_training_status_paused",)),
    Resource("sensor_and_calculated_metrics", ("get_garmin_recovery", "get_garmin_coaching_day", "get_session_with_context"),
             boundary="HRV, stress, Body Battery, readiness, VO2, thresholds, predictions, daily totals, stages and scores have no registered direct setters."),
    Resource("recorded_samples", ("get_activity_samples", "get_activity_splits"),
             boundary="No verified arbitrary sample/lap editor; do not silently replace or reimport recordings."),
    Resource("analysis", ("get_training_summary", "assess_garmin_strength_session", "analyze_garmin_daily_recovery", "compare_garmin_workout_outcomes", "analyze_garmin_lifestyle_association"),
             boundary="Correct eligible sources and recompute. User overrides retain source=user; no Garmin-score overwrite."),
    Resource("local_archive", ("list_archived_activities", "get_archived_activity_analysis", "compare_garmin_intervals", "archive_garmin_activity"),
             boundary="Local storage/analysis; respect archive policy, not a Garmin-account record.", local=True),
    Resource("reference_and_builders", ("list_garmin_activity_types", "find_garmin_exercises", "get_garmin_workout_schema", "list_garmin_workout_sports", "build_garmin_workout", "get_garmin_activity_schema", "build_garmin_manual_activity", "build_garmin_yoga_step", "build_garmin_strength_step", "build_garmin_strength_workout", "build_garmin_running_workout", "build_garmin_swim_workout", "get_garmin_coaching_guide"),
             boundary="Catalogs/schemas are reference data; builders produce drafts for existing create/update operations."),
    Resource("write_workflow", ("get_garmin_capabilities", "get_garmin_write_schema", "get_garmin_write_status", "prepare_garmin_write", "commit_garmin_write", "commit_garmin_workout_creation", "commit_garmin_workout_schedule", "commit_garmin_training_calendar", "commit_garmin_workout_update", "commit_garmin_workout_rename", "commit_garmin_workout_delete", "commit_garmin_existing_workout_calendar"),
             boundary="Fixed operation dispatcher and durable evidence; not an editable account data resource."),
    Resource("connection", ("connection_status",), boundary="Local diagnostics; does not verify Garmin authentication."),
)


def describe(resource, writes, exposed, remote_write_allowed):
    """No account calls. Policy checks report availability without escalating it."""
    from .writes import OPERATIONS
    selected = [r for r in RESOURCES if resource in ("all", r.name)]
    if not selected:
        raise ValueError("Unknown capability resource")
    result = []
    for r in selected:
        operations = []
        for operation in r.operations:
            if operation not in OPERATIONS:
                raise ValueError("Capability registry/operation allowlist mismatch")
            try:
                writes.require_enabled(operation)
                policy = True
            except RequestError:
                policy = False
            operations.append({"operation": operation, "allowed_by_local_policy": policy,
                               "commit_exposed_by_profile": "commit_garmin_write" in exposed,
                               "remote_write_grant_present": remote_write_allowed,
                               "evidence": "native_contract_observed" if operation in {"set_lifestyle_auto_logging", "update_sleep_times", "set_sleep_note", "clear_sleep_note", "add_sleep", "add_nap", "update_nap", "delete_nap", "delete_activity", "delete_weight_measurement", "delete_blood_pressure_measurement", "adjust_hydration"} else "prior_live_acceptance",
                               "schema_tool": "get_garmin_write_schema",
                               "target_reader": ("get_garmin_record_mutation_target" if operation in {
                                   "delete_activity", "delete_weight_measurement", "delete_blood_pressure_measurement", "adjust_hydration"}
                                   and "get_garmin_record_mutation_target" in exposed else r.target if r.target in exposed else None)})
        result.append({"resource": r.name, "read_tools": [name for name in r.reads if name in exposed],
                       "registered_writes": operations, "editable_fields": list(r.fields),
                       "target_reader": r.target if r.target in exposed else None,
                       "boundary": r.boundary, "local_resource": r.local,
                       "unregistered_candidates": list(r.planned)})
    return {"resources": result, "account_request_sent": False,
            "warning": "Candidates are not callable operations. Prior acceptance does not prove every account/device/date variant. Transport acceptance, readback and physical sync are distinct."}
