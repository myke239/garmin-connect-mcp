# Strength-first recovery and coaching

[Documentation home](../README.md) · [Research and metric inventory](../development/coaching-research.md)

Version 0.16.1 provides six read-only coaching tools and two skills. These are an
evidence foundation, not a validated strength-performance prediction model or a
clinical assessment of physical health. Data is processed in memory, with no
coaching archive or account writes. Original fetched dates, units, missingness
and analytical limitations remain visible.

## Daily workflow

Start with `get_garmin_coaching_guide()`. It returns installed nested schemas,
metric units/bounds, source workflow and four runnable synthetic examples.
Example arguments can be copied into the named offline tools; they never contact
Garmin/MFP. Demonstration dates/values are not the person's evidence. The
acceptance tests execute these contracts through MCP with independent numerical
expectations for percentiles, nutrition, strength overlap and unknown data.

Use `get_garmin_coaching_day(calendar_date, timezone)` for each required date.
There are six fixed source reads per day: sleep, HRV, daily statistics,
respiration, stress and morning readiness. Collection stops on authentication,
access or rate-limit failures; other unavailable sources are explicitly marked.
Only scalars with confirmed matching Garmin calendarDate are normalized. Sleep
keeps Garmin's wake-date convention. Readiness must have AFTER_WAKEUP_RESET.
Negative sentinels, unavailable fields and unconfirmed dates are excluded.
The timezone is a caller-confirmed date context, not a conversion of Garmin data.

Pass the returned `day` objects to `analyze_garmin_daily_recovery` with the target
date, same timezone, optional MFP nutrition projections, check-in and ordered
planned sessions. Baselines use prior 14–90 days, default 28, require 14 matching
observations, and exclude the target day. The output describes the current value
against prior median/p10/p90; these are not clinical normal ranges.

MFP integration is orchestrated by the caller/skill through the existing
MyFitnessPal MCP `get_food_diary`. The Garmin server does not access MFP cookies,
import another checkout or make arbitrary cross-server requests. Supply only
date, confirmed timezone, complete, totals and goals; remove diary usernames,
notes and meals. Use the same person's owner diary. Calories are kcal; macros
are grams. The server cannot verify the identity/provenance of submitted evidence.
Completion is user-reported; goal differences are not energy balance. Imported
exercise calories are never added. Future dates, duplicate days and timezone
mismatches fail validation. Day summaries fetched later are not prospective
as-of snapshots and must not be used as if collected before the workout.

## Strength-specific workflow

`assess_garmin_strength_session` takes an offset-aware `as_of`, up to 500 dated
recent sets, up to 30 planned exercises and up to 11 regional check-ins.
Confirm exact exercise/equipment IDs and muscle-region mappings. Reports count
overlapping work sets in the last 24/48/72 hours, time since last work set,
reported RIR, exact-exercise/equipment volume when kg is known, and overlap with
earlier planned exercises. Warmups are excluded. The windows and RIR groups are
descriptive choices, not validated recovery deadlines. No recovery percentage,
exact repetition forecast or fatigue penalty is calculated.

The legacy `get_strength_sets` weight unit is `garmin_raw_unverified` and its
rows lack exact timestamps/RIR. Do not convert raw weight to kg or fabricate set
times from activity start. Use independently confirmed units/timing/effort, or
leave the corresponding evidence unavailable. Regions are caller-confirmed, not
inferred from a similar exercise name. Null load/effort is unknown, not zero.

`compare_garmin_workout_outcomes` describes matched historical sessions. At least
five completed sessions are needed for a median/p10/p90 reference; incomplete
sessions remain in counts. Match movement, load, equipment, ROM, rest, workout
position and effort context. Its range is not a calibrated prediction interval.

`analyze_garmin_lifestyle_association` describes one field's positive presence
versus explicitly recorded zero at lag 0–3 days. Missing is unknown. Seven days
per group is only a display minimum; confounding and multiple testing are not
adjusted. No causation, medication-effect estimate or treatment advice follows.

## Skills and next gates

`daily-performance-coach` combines dated physiology, nutrition and strength
exposure with the user's goals. `review-training-recovery` reviews trends and
matched outcomes. Skills do not authorize account changes or edits to coaching
automations. They request material missing context and distinguish observations,
calculations and coaching judgment.

See the research record for sources and the future prospective validation gate.
Numerical outcome prediction, muscle-recovery timelines, nutrition prescriptions,
adjusted lifestyle causal analysis and a medical health score remain unimplemented.
Use reported symptoms and actual warmup performance as context; favorable
wearable readings do not clear reported pain or illness.
