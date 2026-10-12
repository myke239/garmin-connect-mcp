# Local recording archive and workout management

Enable archive storage locally with the installed launcher `archive-enable`;
`archive-disable` stops access without deleting prior records. This capability
reads Garmin and writes local files; it does not require Garmin write scope.
`archive_garmin_activity(activity_id, retain_raw_fit=false)` downloads the SDK
ORIGINAL ZIP, validates FIT length/checksum and decodes at most 50,000 records.
Exactly one FIT file is accepted, with a 16 MiB compressed/uncompressed bound.
Archive paths are never extracted from ZIP filenames.

Default records contain timestamps, HR bpm, watts, cadence rpm, speed m/s,
elevation metres and distance metres. Coordinates, device serial numbers,
developer fields and free text are omitted. Original FIT retention is a separate
explicit choice and may retain GPS. Records use Windows DPAPI or Linux owner-only
storage. Treat Linux backups as sensitive; permissions alone are not encryption.
Re-archiving replaces that activity's local record, including its raw-retention
choice. `list_archived_activities` pages metadata; analysis never returns raw FIT.

`get_archived_activity_analysis` computes 5/30/60/300/1200-second power best efforts
only from contiguous approximately 1 Hz samples, including measured zero watts.
Missing power invalidates a window. HR/speed drift uses equal-time halves only
with at least 600 fully paired contiguous seconds. It is a whole-session
observation, not proof of steady effort or a diagnosis. Sparse recordings return
unavailable values, never fabricated estimates. No CTL/ATL/TSB is inferred.

`get_activity_samples` supports heart_rate, power, cadence, speed and elevation,
up to 1,000 points. These Garmin chart responses may be downsampled; use archived
full-resolution analysis for power windows. `compare_garmin_intervals` compares
caller-selected lap indices across 2–5 sessions. Select equivalent work laps;
it does not guess whether a lap is a work interval or recovery.

`clone_garmin_workout` produces a draft with executable content preserved and
server-owned IDs removed. Prepare `create_workout` to save it. For renaming or
deletion, call `get_garmin_workout_mutation_target`, then use its exact ID, name
and expected content hash in the corresponding write schema. A fresh mismatch
rejects the mutation. Renaming preserves the full template. Deletion is
irreversible and may remove associated calendar entries; explicitly approve
that effect and supply confirm_calendar_removal=true. Never delete merely
because a similarly named template exists.

`schedule_existing_workouts` accepts 1–20 workout_id/date_str pairs. It creates
no templates. Duplicate pairs and already-scheduled targets are rejected.
Batches are not atomic; completed entries are journaled individually. An unknown
outcome must be investigated before any new intent. All lifecycle writes use the
existing preview/approval/commit workflow and operation-specific commit tools.

Verification (2026-10-12): live synthetic clone, rename, existing-calendar batch,
and deletion passed; all synthetic templates/entries removed. One existing
recording passed SDK ORIGINAL download, FIT decoding, sanitized archive and
channel parsing checks; its temporary archive was removed. Physical watch
execution is not established by these tests.
