# Recovery and workout builders

[Documentation home](../README.md)

`get_garmin_recovery(kind, calendar_date)` exposes sleep, HRV, stress,
body battery, readiness, training status, VO2 max, thresholds, race predictions,
heart-rate zones, daily summary and personal records. Undated SDK endpoints
return latest available records with their original dates. They do not imply
that a measurement occurred on the requested date. Garmin devices may lack a
metric; missing is not zero. Lists and nesting are bounded, raw timelines,
account/device identifiers and feedback text are omitted.

`get_session_with_context` joins a completed activity, splits, zone time and
recovery. Sleep uses Garmin wake dates; a session before 04:00 defaults to the
preceding wake date. Supply `sleep_calendar_date` for shift work or a different
night. SDK morning readiness may fall back to the first snapshot; the response
marks whether AFTER_WAKEUP_RESET actually confirms a morning reading. Partial
network failures are disclosed; authentication/rate errors stop the bundle.

Garmin load/readiness fields are observations, not an independently computed
CTL/ATL/TSB model or a diagnosis. Threshold speed and recoveryTime remain raw
units until independently verified. Sleep duration is seconds, HRV milliseconds,
HR bpm. Responses disclose cache/source timestamps.

High-level pure builders:
- `build_garmin_strength_workout`: exact catalog category/exercise, sets, reps
  OR duration_seconds, optional weight_kg/rest_seconds/notes. Expanded individual
  sets and between-set rests; never substitute another exercise.
- `build_garmin_running_workout`: duration or distance intervals with repeats,
  recovery, warmup/cooldown and HR zone OR ordered seconds/km pace bounds.
  Converts pace to Garmin metres/second.
- `build_garmin_swim_workout`: 25m/50m pools, whole-length distances, strokes,
  drills, equipment and seconds/100m pace bounds with explicit repeats/rests.
  Rest steps use Garmin fixed.rest; pace targets use metres/second in Garmin's
  canonical faster/slower order.

All return drafts, never write. Use existing prepare/approval/commit/readback
workflow. At most 100 expanded steps; timed-only drafts have computed duration,
distance/reps/lap-ended duration remains unknown. Template readback does not
prove physical watch execution, animation or firmware compatibility.

Verification (2026-10-12): Windows 382 tests passed (two Linux-only skips);
Ubuntu 22.04 WSL passed all 384 tests and installed-package MCP discovery/401
checks. Live SDK reads covered all twelve recovery kinds. Synthetic strength,
running and swimming templates passed create/readback checks, including all
five swimming strokes, five equipment types and three drills. All synthetic
templates were deleted and their absence verified. Physical watch execution
remains unverified.

For corrections, use `get_garmin_capabilities` and the [sleep/correction workflow](sleep-and-corrections.md). A dated recovery read is not an arbitrary metric setter. Correct supported source records and refresh analysis; Garmin recalculation and device synchronization remain separate.
