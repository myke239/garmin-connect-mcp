# Workout authoring evidence and device limits

Research checked 2026-10-27. Connect JSON, FIT workout files, and watch execution
are different interfaces. Do not transfer enum numbers or unit encodings between them.

| Source | Finding and authoring consequence |
| --- | --- |
| [Garmin custom workout guide](https://support.garmin.com/en-GB/?faq=wZ52AaLbLG2GC1Lxu2l4k7&productID=777655&tab=topics&topicTag=region_training) | Steps encode a duration and optional target. The guide describes 50 steps, repeat counts up to 99, and device-dependent skip-last-recovery support. Prefer compact repeats; verify the specific watch's capabilities. |
| [Garmin TrainingPeaks workout limits](https://support.garmin.com/en-GB/?faq=CfEpjFFQlb18lvv8Zyw0M7) | Garmin recommends repeats to stay within the documented 50-step device limit. Its warning about TrainingPeaks edits not automatically resyncing is specific to that integration, not evidence about direct Connect template updates. |
| [Garmin pool-swim enhancements](https://support.garmin.com/en-AU/?faq=fXDWMUWcuw5ACMmLqjjC59) | Updated swim workouts support 100 steps; incompatible devices can ignore the last-rest setting. Do not treat 50 or 100 as universal across sports and firmware. |
| [Garmin Venu 4 strength instructions](https://www8.garmin.com/manuals/webhelp/GUID-2CF5620C-E585-4E0A-9CC3-9565533EEE4D/EN-US/GUID-49D892BF-429E-454D-B0C6-D4AE07E9D4A0.html) | One move per set, manual set completion and rep/load corrections matter. Arm-motion rep counting may miss leg exercises. A prescribed rep count is not a verified completed count. |
| [Official FIT workout specification](https://developer.garmin.com/fit/articles/file-types/workout.html) | Steps have explicit duration/target semantics and repeat references. FIT uses its own message indices, enum values and scaled target encoding; these are not Connect JSON IDs or units. |
| [Python Garmin Connect workout source](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/workout.py) | Compare against the repository's pinned `garminconnect==0.3.17`, rather than upgrading assumptions from mutable master. Pinned helpers supply repetition/time/iteration IDs, unique step ordering. Its kg-to-gram planned load conversion and ascending `PaceTarget` bounds were initially copied but contradicted by user-reported Connect display evidence on 2026-11-10; the connector now overrides both conventions. Newer upstream explicitly supports `skipLastRestStep`; 0.3.17 permits it as an extra DTO field. |

Implementation choices: the connector retains its bounded 100 stored-step
validator and five-level nesting limit. Builders use at most 99 iterations and
warn above 50 stored nodes, counting groups and children conservatively. This
is a compatibility warning, not a device certification. Repeat counts do not
multiply the stored-node count. Run duration calculations do multiply executed
children and remove only the explicitly skipped final rest.

The 60-second set rest and 120-second transition are configurable authoring
defaults requested for this plugin, not research-derived exercise prescriptions.
Timed holds describe intended intervals; they cannot establish successful hold
time, form quality or effort. Keep measured activity outcomes separate.

Offline acceptance verifies DTO structure and synthetic save/readback/calendar
behavior. It cannot establish a real account's acceptance, on-watch labels,
animations, skip-last-rest execution or physical sync. Report those limits
until a separately authorized device check establishes them.

## Follow-up evidence — 2026-11-10

The user reports API readback and Garmin Connect displaying a 14-mile distance
step with 9:15–11:30 /mi boundaries when targetValueOne is the faster speed.
They also report correcting 1,000-fold planned strength loads by dividing the
encoded value by 1,000. These are user-reported observations, not screenshots
independently inspected in this implementation session. Regression fixtures
encode those observations; they are not proof of every sport/device combination.
Instinct 2 out-of-range vibration remains untested. Swimming shares pace.zone
encoding, but its app display and device behavior require separate verification.

Garmin's [custom workout guidance](https://support.garmin.com/en-GB/?faq=wZ52AaLbLG2GC1Lxu2l4k7&productID=777655&tab=topics&topicTag=region_training)
describes pace ranges, repeats up to 99 and device-dependent secondary targets
and workout splits. Its [swim enhancements](https://support.garmin.com/en-CA/?faq=fXDWMUWcuw5ACMmLqjjC59)
describe optional final rest in repeat blocks. The
[FIT workout specification](https://developer.garmin.com/fit/articles/file-types/workout.html)
separates step duration from targets; its low/high FIT fields must not be assumed
to have the same ordering or scaling as Connect JSON. Public Garmin guidance
does not document the private Connect JSON pace/load conversion.
