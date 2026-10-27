# Garmin SDK workout shape

The MCP accepts SDK-named operation parameters. `upload_workout(workout_json)`
forwards JSON unchanged; it does not fill in enum IDs or fix units. The source
for these conventions is the pinned SDK's `garminconnect/workout.py`.

Read a full existing template when possible. A workout needs `workoutName`,
`sportType`, and `workoutSegments`. Each segment has `segmentOrder`, `sportType`,
and `workoutSteps`. Pair numeric enum IDs with their keys:

| Object | ID field | Key field | Running example |
| --- | --- | --- | --- |
| sportType | sportTypeId | sportTypeKey | 1 / running |
| stepType | stepTypeId | stepTypeKey | 3 / interval |
| endCondition | conditionTypeId | conditionTypeKey | 3 / distance |
| targetType | workoutTargetTypeId | workoutTargetTypeKey | 1 / no.target |

SDK step types: warmup 1, cooldown 2, interval 3, recovery 4, rest 5, repeat 6.
End conditions: lap.button 1, time 2, distance 3, iterations 7, reps 10.

Executable steps use `type: ExecutableStepDTO`, positive `stepOrder`, and those
step/condition/target objects. A time or distance step needs positive
`endConditionValue` **on the step**, in seconds or metres. Never put it inside
`endCondition.conditionValue`. Convert miles using exactly 1609.344 metres per
mile; 12 miles is 19312.128 metres. Do not infer a duration for a distance step.

No target uses ID 1 and key `no.target`. The pinned SDK's PaceTarget and
SpeedTarget use **metres/second**, with slower speed as targetValueOne and faster
speed as targetValueTwo. Convert pace by distance metres / duration seconds;
for example 8:00/mile is 1609.344 / 480 m/s. Heart-rate range targets use bpm,
power ranges watts, cadence steps/revolutions per minute; numbered zones require
zoneNumber from the user's actual settings. Copy a known valid template's
target structure before editing it. Natural-language RPE or pace text is advisory,
not a machine-enforced target.

Repeat groups use `type: RepeatGroupDTO`, `stepType` 6 / repeat,
`numberOfIterations`, and nested `workoutSteps`. The SDK helper also supplies
`endCondition` 7 / iterations and `endConditionValue` equal to the repeat count.
Include those when building a group. All child steps need complete enum objects
and values. Use globally unique preorder `stepOrder` values; builder groups
and their executable children share a `childStepId`, distinct for each group.
Preserve server-issued IDs on unchanged template groups. `skipLastRestStep`
must be a boolean and applies only to a final rest/recovery child.
Server limits: 100 stored steps, five nested repeat levels, 1–100 iterations
(builders use 1–99). Create/update parameters may use up to 256 KiB;
calendar batches up to 2 MiB with at most 20 individually valid templates.
These are connector bounds, not Garmin/watch guarantees; see
[research and device limits](workout-research.md).

Build compact JSON by omitting unnecessary null/default fields for new templates.
Do not strip unrelated metadata from a complete update just to fit a limit.
If an update exceeds its bound, report the specific validation issue; do not
replace it with a new template or a new key after an uncertain write outcome.

## Simple distance run

The adjacent [easy-distance-run.json](easy-distance-run.json) is a validated
5 km untargeted run. Change the name and distance to the user's requested
values; its presence is not authorization to upload it. Wrap the object in
`{"workout_json": object}` for standalone creation or `{"workouts":
[{"date": "YYYY-MM-DD", "workout": object}]}` for a calendar batch.

Do not fabricate required workout fields for sports not represented by this
example. Retrieve an appropriate template or explain what evidence is missing.
