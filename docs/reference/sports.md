# Workout sports and recorded activities

[Documentation home](../README.md)

A planned workout is a template that can be saved, edited, scheduled, or queued
for a compatible device. A manual activity is a private log of an already
completed session. These use different type catalogs and APIs. Never create a
future activity to stand in for a workout, or silently change an unsupported
requested sport to a different sport.

## Planned workouts

`list_garmin_workout_sports` queries Garmin's current workout-type metadata and
reports schema availability. `get_garmin_workout_schema(sport)` returns a complete
`example_workout`, a Pydantic-derived `json_schema`, IDs, limits and workflow
instructions. Local operation validation applies additional enum, target,
count, unit, nesting and payload-size checks beyond the base JSON schema.

| Workout sport | ID |
|---|---:|
| running | 1 |
| cycling | 2 |
| other (custom) | 3 |
| swimming | 4 |
| strength_training | 5 |
| cardio_training | 6 |
| yoga | 7 |
| pilates | 8 |
| hiit | 9 |
| multi_sport | 10 |
| mobility | 11 |
| rucking | 13 |

Each was verified with create, update, readback, calendar scheduling,
unscheduling and deletion of a temporary synthetic template on 2026-10-12.
This verifies basic structured sessions, not every advanced target or device.
Timed sessions encode duration only. They do not encode poses, swimming strokes,
pool/equipment settings, HIIT timer formats, animation or ruck pack load merely
because those appear in a name or description. Copy verified sport-specific
fields for those features. Strength uses exact exercise pairs and the strength
step builder for repetitions and planned kg loads.

For a user-requested 20-minute Pilates session:

```json
{"sport":"pilates","workout_name":"Requested Pilates","duration_seconds":1200}
```

Pass this to `build_garmin_workout`. It returns validated `workout_json` and makes
no Garmin request. Prepare `create_workout` with that JSON, authorize the exact
preview, commit its draft and read back the saved template. Schedule its verified
ID using `schedule_workout` parameters `workout_id` and `date_str`, or prepare
`create_training_calendar` with dated templates. Examples are not authorization
to save. Always use the user's name, duration, date and timezone.

For an explicit step plan, supply `workout_segments` instead of duration_seconds.
Use complete returned enum/DTO fields; the builder does not invent advanced
fields. A single-sport segment must match its header. Multisport requires the
user's explicit constituent sports/segments; its example run-bike choice is
illustrative. All multisport stepOrder values must be globally unique, including
nested steps; do not restart numbering in each leg. Duplicate orders caused an
upstream 400 in the initial test, and are now rejected locally. That initial
unknown write was searched across the complete library with no matching test
found before the corrected payload was tested under a separate test intent.

Walking/hiking SDK workout IDs 17/18 are **unsupported**: neither is advertised
by Garmin's workout catalog, and both live test templates read back with sport
ID 0 and null key. Those templates were deleted. Creation is now blocked instead
of silently saving a template with lost sport identity. Completed walking/hiking
manual logs remain supported. Do not substitute running or other without the
user selecting that alternative.

Device push accepts an explicit ID from list_garmin_devices. Successful queuing
is not proof of device download or sport compatibility. New unrecognized live
workout sports are reported with schema_available false until their schema is
implemented and tested; no guessed IDs are accepted.

## Completed activity logs

`list_garmin_activity_types` exposes Garmin's live recorded-activity type tuples.
`get_garmin_activity_schema(type_key)` returns the exact type's manual-creation
contract, parameter template, eligibility and limits. The contract fixes type_key
to that exact catalog value. `build_garmin_manual_activity(parameters)` validates
complete parameters against the live catalog without an account mutation.

The inspected catalog contains 154 types. 139 are eligible for this shared manual
log path; 15 restricted/system types are blocked. Counts may change: use the live
catalog, not this document as an exhaustive list. Activity keys may differ from
workout keys, such as indoor_cardio versus cardio_training or lap_swimming versus
swimming. Membership and local validation alone do not guarantee upstream
acceptance for every data variant.

Manual parameters are:

- type_key: exact live recorded-activity key.
- activity_name: user's requested name.
- start_datetime: actual local timestamp, without offset; milliseconds normalized.
- time_zone: actual IANA timezone, with DST ambiguities rejected.
- distance_km: actual distance, explicitly 0 when none was measured.
- duration_min: actual whole minutes; do not silently round a measured duration.

Prepare `create_manual_activity` with the builder's parameters, authorize the
preview, commit and verify the returned activity ID with a fresh read. These logs
cannot be scheduled as future workout templates. Basic manual fields do not
encode GPS, sets, swimming strokes, dive telemetry or other unmeasured metrics.
Use a user-supplied FIT/TCX/GPX recording for richer imports, following its schema
and the account-management skill. No activity deletion tool is exposed; live
audit cleanup operates only on its explicitly authorized synthetic fixtures.

Unknown outcomes stop dependent writes and require reconciliation; never retry
through a new intent key. The builder and schemas do not grant write permission:
local policy (writes default to enabled) and remote garmin:write still apply.

## Release audit evidence

Version 0.6.0 validation on 2026-10-12:

- 241 offline tests, including schemas for every supported workout sport, builders,
  read-only MCP discovery, type-specific contracts and invalid-input guard cases.
- All 12 advertised workout sports: create, update, readback, calendar scheduling,
  unscheduling and deletion of each synthetic template.
- All 139 eligible live recorded-activity types: private manual creation with a
  synthetic one-minute/one-metre fixture, matching activity-type readback and deletion.
- Additional zero-distance yoga, Pilates, strength and mobility logs: creation,
  matching readback and deletion. These check stationary session inputs.
- All 15 restricted/system catalog types excluded from manual creation; builder
  and commit-preflight guards tested without creating safety events.
- Complete library/calendar and audit-date activity searches found no remaining
  fixtures. Initial unknown multisport outcome had no matching template in the
  full bounded library search; its journal outcome was retained rather than reset.

These are basic payload acceptance checks, not proof of every advanced field,
historical timestamp, imported data variant or physical watch capability.
No credentials, private account statistics or account identifiers are published.
