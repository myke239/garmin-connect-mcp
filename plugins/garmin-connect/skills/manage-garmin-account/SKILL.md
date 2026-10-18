---
name: manage-garmin-account
description: Create manual Garmin activity logs for completed sports sessions, edit sleep times/notes and current-day naps, correct hydration, delete exact activity/measurement records, edit activities or strength sets, import activity files, record actual health measurements, manage Lifestyle logs/custom behaviors/tracking, or send saved workouts to a device using guarded Garmin Connect MCP writes.
---

Use the Garmin Connect MCP server for account changes. Before preparing an operation, call `get_garmin_write_schema(operation)` and follow its current names, types, units, bounds and verification guidance. The server owns SDK calls; do not bypass it with direct HTTP, SDK scripts or journal edits. For workout construction/calendar workflows, use the plugin's `create-schedule-workouts` skill.

Honor the user's authorized scope. Establish the exact target and content before writing, show the preview, and commit only with authorization covering it. Existing explicit authorization for a bounded test or identical payload need not be requested again. Examples and proposed coaching advice are not measurements or permission to save them.

## Capability and target discovery

Start with `get_garmin_capabilities` for resource writes, current policy/profile,
remote grant and target readers. Listed unregistered candidates cannot be called.
Use the operation's current schema, not a guessed setter or arbitrary SDK/HTTP
call. Readback, transport acceptance and watch sync are separate claims. New
commits include verification metadata; old journal entries are not retroactively
verified. Never create a second intent to retry an unknown/in-progress result.

## Sleep and naps

Read `get_garmin_sleep_mutation_target(calendar_date)` freshly. The date is the
local wake/end date. Copy its ID/hash for `update_sleep_times`, `set_sleep_note`
or `clear_sleep_note`. `add_sleep` needs the fresh absent-record hash and must
not replace existing sleep. It creates duration only and cannot normally be
deleted: never use a fabricated main sleep as disposable live test data.

Time writes require whole-second ISO start/end with explicit offsets plus an
IANA `time_zone`. The server checks DST offset agreement, elapsed UTC duration
and end date. Main sleep windows are completed 1 minute to 24 hour intervals.
Target endpoints are epoch milliseconds; write inputs are ISO strings. Time
editing preserves original native local endpoints, confirmation type, stages,
scores and note; Garmin owns recalculation. Do not manufacture score/stage data
or edit the device's usual bedtime schedule through a dated sleep operation.
Setting a note replaces the full text; clearing a note does not delete sleep.

Read `get_garmin_nap_mutation_target(calendar_date,time_zone)` for current-day
naps and the full-list hash. `add_nap`/`update_nap` need completed same-day
5 minute to 3 hour windows without sleep/nap overlap. Updates/deletes use the
original `nap_start_ms`; do not substitute the proposed new start. Delete also
needs `confirm_delete=true`. The day gate is rechecked before send, so a draft
can become ineligible at midnight. Native offsets are minutes; the server owns
UTC-string conversion and native account/device context.

These new native contracts have offline tests but no live mutation acceptance
claim. For any real-night correction, establish the exact requested change;
implementation or analysis permission alone is not permission to modify health
history. Inspect returned readback evidence, then refresh the target. Report
Garmin recalculation and physical synchronization as unverified unless separately
observed.

## Exact deletion and hydration corrections

Use `get_garmin_record_mutation_target(kind,calendar_date?,record_id?)`.
Activity needs record_id only; weight/BP/hydration need calendar_date only.
Deletion requires explicit scope covering the exact returned record, fresh hash
and `confirm_delete=true`. `delete_activity` also needs its exact old name.
Use each weight sample's native ID or BP version, never an average or inferred
identifier. Weight deletion removes attached composition too. No bulk delete,
silent delete/recreate editor or automatic compensating write is available.
Local activity archives remain after account deletion.

`adjust_hydration` is a nonzero signed ml delta within +/-10,000, with fresh dated
total hash and explicit-offset timestamp on that local date. The resulting total
must remain nonnegative. `add_hydration` remains positive-only. Verify the daily
total; do not invent a per-drink deletion identity or turn a correction into an
absolute overwrite. Concurrent external changes can make readback uncertain.

## Activity edits and imports

Read `get_activity_edit_template(activity_id)` before name, description, type or strength changes. Verify the ID, not just the name. Use `list_garmin_activity_types` for the complete typeId/typeKey/parentTypeId tuple. Server preflight rejects nonexistent targets and mismatched catalog tuples.

Strength replacement takes the complete original `exercise_sets_payload`, with a matching activity ID. Preserve untouched sets, timestamps, UUIDs and metadata. Use `find_garmin_exercises` for valid category/exercise names; a known category with null exercise name is allowed. Foreign set IDs are rejected. Do not convert `weight` without verified units: recorded set weights are Garmin raw units. An empty array clears every set and needs explicit authorization for that effect.

For a requested completed-session log, call `list_garmin_activity_types`, choose
its exact typeKey, and read `get_garmin_activity_schema(type_key)`. This returns
that type's creation contract and parameter template; type keys can differ from
workout keys (for example activity `indoor_cardio` versus workout `cardio_training`).
Do not copy placeholder values or invent measurements. Pass actual parameters to
`build_garmin_manual_activity`; prepare its returned parameters with
`create_manual_activity`, review/authorize, commit, then read the returned activity
ID. Schema membership is not proof of upstream acceptance for every variant.
Restricted/hidden catalog types, aggregates, safety events and transitions are
blocked. Do not create a future activity log to simulate a scheduled workout.
If the desired sport has no workout schema, explain the planning limit rather
than silently changing its sport. Manual logs cannot be scheduled on the calendar.

Manual activities use a local timestamp with an IANA timezone, km and whole minutes. The server normalizes milliseconds and rejects ambiguous/nonexistent daylight-saving times. It creates a private activity. The live audit accepted basic logs for all eligible types and current-date zero-distance yoga/Pilates/strength/mobility. An older historical strength/zero-distance variant failed upstream; do not promise every data or timestamp variant will be accepted.

Import only a user-provided recording (or an explicitly authorized synthetic test). Supply base64 bytes and fit/tcx/gpx, never a host file path. FIT checks CRC and uses the pinned official Garmin FIT decoder to require activity/session/lap messages; health and course files are rejected. XML needs timestamped tracks with positive elapsed time and rejects entities. Format validation cannot guarantee Garmin import success; GPS may enter the conversation/service.

Garmin imports may be asynchronous and return no IDs. `completed` then means the SDK returned without error, not that every record is already visible. Search the relevant date with `list_activities`, follow cursors and match timestamp/duration/distance and other evidence. Use a fresh read; report pending verification instead of creating a duplicate. Never identify a match solely by name.

## Measurements and devices

Use actual user-supplied measurements and explicit timestamp/offset. Never estimate weight, composition, hydration or blood pressure from exercise data. Omit unmeasured optional fields. Query schemas for units: weight input kg/lbs, composition mass kg, percentages, energy kcal/day, hydration ml, blood pressure mmHg/pulse bpm. FIT encoding bounds are technical limits, not medical advice. Hydration date must agree with the timestamp's local date. Verify one-day entries with `get_garmin_measurements`; raw weight responses may be grams, even when input was kg. Composition imports can take time to appear.

For device push, read `list_garmin_devices`, confirm the requested device, and specify both IDs. Preflight checks membership. A successful commit confirms queue acceptance, not physical download or watch sync. Do not send to an implicitly selected device.

## Lifestyle logs and custom behaviors

Use `get_garmin_lifestyle_mutation_target(calendar_date, behaviour_id?)` for a
fresh dated catalog and catalog hash. Include the exact behavior ID to get its
daily log and log hash before set/clear. `list_garmin_lifestyle_fields` is only a
partial daily view; do not use it as a full definition catalog. Preserve exact
names and raw amounts; do not infer medication units or recommended doses.

Query the current schemas for `create_lifestyle_behaviours`,
`rename_lifestyle_behaviour`, `delete_lifestyle_behaviours`,
`set_tracked_lifestyle_behaviours`, `set_lifestyle_log`, `clear_lifestyle_log`
and `set_lifestyle_auto_logging`. Prepare through `prepare_garmin_write`, review
the exact preview, then use generic `commit_garmin_write` with authorization.

Creation supports custom yes/no (NONE) and integer quantities (QUANTITY), with
sleep-related selection. Discover assigned IDs afterward; adding a definition
and enabling its tracking are separate intents. Tracking replaces the COMPLETE
list for that date: retain every existing ID the user still wants. [] untracks
all. Order is sent but only membership readback is verified. Do not silently
fall back to today's date when a historical date is rejected.

Daily set replaces a summary, not appends an event. Garmin rejects zero-quantity
writes: use positive integer amounts only. Preserve zeros returned on reads;
never substitute NO or clear for a requested zero. NO and clear are separate intents. A quantity with subtypes requires their exact catalog IDs.
The IANA timezone is for current updateTimestamp, not a claimed consumption time.
Copy fresh hashes into the expected fields and get new evidence after each
write. Reject stale evidence instead of rebasing approved content automatically.

Custom definition deletion may erase historical logs. Obtain explicit approval
covering exact IDs/names and possible history loss; prefer untracking to retain
history. Built-in definitions cannot be renamed/deleted. Catalog absence verifies
only removal from that dated catalog, not historical erasure. Do not rewrite a
measurement type after creation. Auto-logging changes only the account global
boolean read by `get_garmin_lifestyle_auto_logging`; mobile reminders and
onboarding/terms acceptance are not exposed.

Synthetic tests require approved harmless test definitions. Never use medication
records as write tests. Stop dependent writes on unknown/in_progress, including
readback failure; do not create a new key to retry an uncertain request.

## Failure and recovery

Use a stable intent key per exact payload. Validation errors say `garmin_request_sent: false`; terminal preflight/validation `rejected` results say `garmin_mutation_sent: false`. Fix the named issue and obtain/reuse authorization for corrected content before a new intent. Do not mistake a preflight read for a mutation.

On `unknown` or `in_progress`, stop dependent writes. Read `get_garmin_write_status(draft_id)` and inspect Garmin with fresh verification tools. Preserve IDs, partial batch steps and safe error categories. Do not retry with a new key or delete the journal. SDK mutation replay is blocked, including after an HTTP 401; reauthorization does not make an old unknown write safe to repeat. Report partial-import failures even if the HTTP request returned successfully.

Bulk activity deletion, gear defaults, reproductive-health configuration and arbitrary SDK/GraphQL requests are not MCP operations. Explain unavailable operations rather than finding a bypass. Authentication, explicit local write-policy denial and remote garmin:write failures require their specific user-facing setup guidance; never request passwords, MFA codes or tokens in chat.

## Reviewable workout commits

Workout preparation returns `commit_tool` and `commit_arguments`. After approval
of the full preview, call that tool with the returned arguments unchanged:
creation uses `commit_garmin_workout_creation`, scheduling uses
`commit_garmin_workout_schedule`, calendar batches use
`commit_garmin_training_calendar`, and replacement uses
`commit_garmin_workout_update`. Name/sport/ID/date fields communicate the action;
content_sha256 binds the full stored payload. Do not invent or recompute these
fields to change an approved draft. Replacement remains destructive.

`commit_garmin_write` remains compatible for old drafts and other operations.
A platform safety block is distinct from a connector error. Preserve the exact
error and draft status; do not switch tools, SDK, or HTTP paths to evade a block.
The new tools improve reviewability but are not a proven safety-block fix.

WRITE_OPERATION_DENIED means the owner's local operation allowlist rejects this write; do not attempt another operation or generic commit to evade it. Tool profiles may intentionally omit features. ARCHIVE_DISABLED needs the owner's local storage choice, never implicit enablement. Catalog drift changes require reviewed updates; do not adopt newly observed identifiers into production automatically.
