# Create and schedule a workout

[Documentation home](../README.md) · [Exact operation contracts](account-writes.md) · [Sport coverage](../reference/sports.md)

A workout is a planned template; a manual activity records a completed session. Do not use a future activity log as a substitute for scheduling. Start with the user's exercises, sport, date and timezone.

## 1. Discover the correct schema and exercise identities

Call `list_garmin_workout_sports`, then `get_garmin_workout_schema(sport)` when using an unfamiliar sport. For strength, search `find_garmin_exercises` and retain the returned category/exercise pair. For yoga use `category="POSE"`. Follow `next_start`/pagination until the selected movement is found; do not replace an unavailable movement with an unrelated one.

The catalogs contain 1,527 strength entries across 47 categories and 85 verified poses. Catalog availability does not establish suitability or watch animation.

## 2. Build without saving

Use the appropriate pure builder:

| Session | Builder |
| --- | --- |
| Running intervals, pace or heart-rate targets | `build_garmin_running_workout` |
| Strength sets/reps, load, rests or timed exercises | `build_garmin_strength_workout` |
| Pool swim lengths, strokes, drills, equipment and pace | `build_garmin_swim_workout` |
| Basic timed workout or explicit Garmin segments | `build_garmin_workout` |
| Exact strength/yoga executable step | `build_garmin_strength_step` / `build_garmin_yoga_step` |

Builders return validated drafts and do not mutate Garmin. Reps, seconds, metres and kilograms have different fields; use the returned schema rather than hand-converting enum IDs. A named custom timed step is supported, but unsupported identities/fields cannot be made valid just by putting them in a description.

## 3. Prepare and review

Query `get_garmin_write_schema(operation="create_workout")`. Prepare the returned `workout_json` with `prepare_garmin_write`, using one stable idempotency key for this intent. Show the full preview: name, sport, exercises, repetitions/timing, loads, rests and any targets. Local writes must be enabled, and remote commits also require `garmin:write`.

After approval of this exact preview, invoke the returned `commit_tool` with its unchanged `commit_arguments`. Do not simplify away review fields. Inspect the durable outcome with `get_garmin_write_status`.

## 4. Verify before scheduling

Read the saved ID with `get_workout_template`. Confirm the requested sport and executable content were retained. Scheduling an existing verified workout uses SDK argument names:

```json
{
  "operation": "schedule_workout",
  "idempotency_key": "schedule-example-2026-10-20-v1",
  "parameters": {
    "workout_id": "123456789",
    "date_str": "2026-10-20"
  }
}
```

This is an example shape; replace the ID/date with the verified template and requested date. `date` and `workoutId` are not accepted SDK argument names here. Check `list_scheduled_workouts` for duplicates, prepare, review the calendar preview, commit, then read that month again.

Use `schedule_existing_workouts` to schedule 1–20 existing ID/date pairs, or `create_training_calendar` to create and schedule new templates. Batches are not atomic; inspect each recorded step before deciding what remains.

## If the outcome is uncertain

A timeout or crash can leave `unknown` or `in_progress`. Check the existing draft and Garmin library/calendar. Do not recreate the workout, generate a new key, or repeat a commit blindly. A platform safety block without a connector response does not establish a Garmin permission failure; preserve the exact message and use [troubleshooting](troubleshooting.md).

For rename/delete, obtain a fresh name/content hash from `get_garmin_workout_mutation_target`. Deletion is irreversible and may remove calendar entries; approve that effect explicitly. Device queueing requires a discovered device ID and still needs physical watch verification.
