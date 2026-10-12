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
End conditions: lap.button 1, time 2, distance 3, iterations 7.

Executable steps use `type: ExecutableStepDTO`, positive `stepOrder`, and those
step/condition/target objects. A time or distance step needs positive
`endConditionValue` **on the step**, in seconds or metres. Never put it inside
`endCondition.conditionValue`. Convert miles using exactly 1609.344 metres per
mile; 12 miles is 19312.128 metres. Do not infer a duration for a distance step.

No target uses ID 1 and key `no.target`. For pace/heart-rate/power targets,
copy a known valid template's target structure and verify numeric units before
editing it. Natural-language RPE or pace text in a description is advisory,
not a machine-enforced target.

Repeat groups use `type: RepeatGroupDTO`, `stepType` 6 / repeat,
`numberOfIterations`, and nested `workoutSteps`. The SDK helper also supplies
`endCondition` 7 / iterations and `endConditionValue` equal to the repeat count.
Include those when building a group. All child steps need complete enum objects
and values. Server limits: 100 total steps, five nested repeat levels, 1–100
iterations, and 12 KiB for an operation's parameters.

## Simple distance run

The adjacent [easy-distance-run.json](easy-distance-run.json) is a validated
5 km untargeted run. Change the name and distance to the user's requested
values; its presence is not authorization to upload it. Wrap the object in
`{"workout_json": object}` for standalone creation or `{"workouts":
[{"date": "YYYY-MM-DD", "workout": object}]}` for a calendar batch.

Do not fabricate required workout fields for sports not represented by this
example. Retrieve an appropriate template or explain what evidence is missing.
