---
name: daily-performance-coach
description: Combine Garmin recovery evidence, MyFitnessPal nutrition and planned running or strength sessions for a daily coaching check-in. Use for training preparedness, not medical diagnosis or account changes.
---

# Daily Performance Coach

Establish the person's intended date, IANA timezone, planned workout sequence and
whether this is a morning or pre-workout check. Preserve their training goal.

Start with `get_garmin_coaching_guide` when discovering the installed contracts.
It returns current nested schemas, units and runnable synthetic examples. Prefer
those contracts over remembered inputs. Examples are not the person's data.

Use `get_garmin_coaching_day` for dated physiology; pass its `day` objects as history
to `analyze_garmin_daily_recovery`. Reuse available evidence and fetch additional
dates in small batches, stopping on authentication or rate-limit errors. Aim for
14–28 prior observations but report insufficient baseline when unavailable.
Never invent missing dates or carry forward yesterday's values. Check fetch
timestamps: daily summaries change during the day, and historical fetches are
not historical as-of snapshots suitable for testing prospective predictions.

If a MyFitnessPal connector is available, call its `get_food_diary` for relevant
dates with `include_notes=false`. Use the owner's diary; confirm both sources
refer to the same person/timezone. If unavailable, request exported data or mark
nutrition unavailable. Do not access browser cookies or alternate account clients.
Project only date, complete, totals, goals and confirmed timezone. Exclude names,
notes, meals and exercise calorie adjustments. Missing nutrients stay null;
completion is user-reported, not proof of completeness. A difference from a diary
goal is not a measured energy deficit; today's log may still be partial.

For strength first call `assess_garmin_strength_session` with confirmed dated work
sets, exact exercise/equipment/region mappings and regional soreness/pain. Review
24/48/72-hour exposure and earlier planned exercise overlap as descriptive
context, never a recovery deadline. `get_strength_sets` currently labels weights
garmin_raw_unverified and lacks set timestamps/RIR: do not infer kg, exact times
or proximity-to-failure. Request independently confirmed evidence or omit it.

Ask for fatigue/soreness (0–10), pain, illness symptoms and workout details when
missing information materially affects the assessment. Unknown symptoms stay
unknown. Submit sessions in intended order. Pain/illness needs review regardless
of favorable wearable values. The current tool does not calculate local muscular
recovery or sequence fatigue. For strength, use exact exercise history, effort
and region-specific soreness when available; do not infer recovery hours from HR.

Use `compare_garmin_workout_outcomes` only for genuinely comparable exercise/load,
interval structure, equipment, terrain, duration and sequence context. Its range
is historical, not a prediction interval. Never manufacture exact pace/reps,
completion probability, injury risk or glycogen level from descriptive deviations.
Separate reported values, calculated comparisons and coaching judgment. Garmin
composites share inputs; HRV, Body Battery, stress and readiness are not independent votes.

For tool input construction and lifestyle comparisons, read
[input contracts](references/input-contracts.md). Medication entries are sensitive
context, not permission to infer effects or recommend changes.

Present the main assessment, supporting drivers, missing information and
workout-specific interpretation with uncertainty. A wellness snapshot is not
medical clearance. This skill does not authorize account writes, medication
changes, recurring tasks or edits to existing coaching automations.
