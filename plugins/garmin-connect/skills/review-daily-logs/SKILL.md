---
name: review-daily-logs
description: Review completed days of Garmin workout, food diary, sleep and lifestyle records for gaps or possible errors, suggest evidence-backed clarifications and track unresolved questions. Supports manual and scheduled reviews without automatic health-record corrections.
---

# Review daily logs

Use `get_garmin_review_guide` for schemas and `analyze_garmin_daily_logs` for
deterministic questions. Establish completed local date and IANA timezone.
For scheduled runs, follow the [run protocol](../schedule-health-reviews/references/run-protocol.md).
For manual reviews, persistence is optional and requires the user's intended
scope; analysis alone does not require configuring a task or saving a profile.

Collect configured sources independently. Confirm same person/timezone across
Garmin and nutrition. Use the available nutrition connector, not browser cookies
or another client. Project kcal, macros in g, completeness and goals; when needed,
inspect bounded meal/serving details without notes. Meal labels are not timestamps.
Only mark a meal expected from a confirmed routine. Repeated similar foods are
not necessarily duplicates; identify exact source entries for clarification.

Use bounded activity pagination, exact activity/set IDs and the Garmin exercise
catalog. Unknown exercise candidates may use the actual plan, adjacent exercises,
equipment and previous user-confirmed corrections. State why a candidate fits;
offer alternatives or abstain when ambiguous. Never infer an exercise from heart
rate alone. Preserve category-only exercises as uncertain rather than invalid.

For load checks, set `comparison_group` only when exercise/equipment, repetitions,
load convention and purpose are comparable. Distinguish warmups, work sets, drop
sets, pyramids, unilateral loads and assistance. Current Garmin set weights are
raw/unverified; leave that unit explicit and skip numeric comparisons until
independently verified. Do not derive kg from plausible-looking values.

Match Lifestyle fields by stable ID and confirmed units. Missing, skipped, present
and unknown are separate states. A supplement amount is the user's reported
routine, not a recommendation; never recommend catch-up doses or infer medication
effects. Use the dated source, not a prior day's value.

Check planned versus recorded workouts, duplicate imports, unrecorded sleep or
device nonwear, naps/overlap, hydration and measurement gaps where configured.
Only put observed discrepancies in `gaps`; absence in a truncated or stale response
cannot establish a missing record. Record unavailable checks in coverage instead.

The analyzer's default low-calorie ratio (0.7) and weight deviation (0.25) are
configurable logging heuristics, not health thresholds. Low logged calories versus
a goal mean a question about diary accuracy, not measured energy deficit or a
diagnosis. Today's unfinished diary must not be processed as a completed day.

Present possible issues with date/record evidence, confidence and a neutral
question. Explain which checks could not run. Persist all findings in scheduled
reports while asking the most consequential questions first. Reuse resolved
answers; do not fabricate entries, autofill habitual intake or rewrite weights.
When a user requests a concrete correction, route to the provider's existing
guarded writes and verify the change before marking corrected.
