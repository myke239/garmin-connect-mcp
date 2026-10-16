---
name: review-training-recovery
description: Review multiweek Garmin training and recovery with MyFitnessPal nutrition, lifestyle records and actual workout outcomes. Use for weekly progression reviews, not automatic training edits or diagnosis.
---

# Review Training Recovery

Establish the review period, timezone, sports and training goals. Gather Garmin
activities with bounded pagination, coaching-day evidence, relevant Lifestyle
fields, and MyFitnessPal nutrition when available. Reuse available evidence and
stop collection on authentication/rate-limit errors. Identify missing watch nights,
incomplete activities and partially logged nutrition before interpreting averages.
Keep source dates/units/coverage/fetch timestamps. Do not store personal health
data in source or assume authorization to create an archive.

Separate training exposure from performance and perceived recovery. Review
endurance and strength separately: cardiovascular load does not establish
muscle/tendon recovery. Preserve exercise, equipment, reps, weight and effort;
do not sum unrelated exercise tonnage as one physiological load. Compare genuinely
matched sessions with `compare_garmin_workout_outcomes`, retaining incomplete
session counts. Historical reference ranges are not validated predictions.
Use `assess_garmin_strength_session` for confirmed work sets, region check-ins and
planned exercise overlap. Never convert garmin_raw_unverified weight to kg or
fabricate per-set timestamps/RIR from activity summaries. Its exposure windows
are descriptive, not muscle-recovery deadlines.

Use `analyze_garmin_daily_recovery` for descriptive comparisons; each baseline
excludes its target day. Garmin composites overlap. Avoid universal HRV targets,
automatic training changes from one outlier and acute:chronic ratios as personal
injury probabilities. Wearable scores cannot establish overall physical health.

For MFP, use the owner's dated totals/goals/completion flag; confirm identity and
timezone, exclude notes, and preserve missing versus zero. Do not add Garmin
activity calories imported into MFP. Goal differences are not energy balance;
food totals do not establish glycogen or diagnose REDs. If the connector is
unavailable, mark nutrition missing rather than inventing values.

Use `analyze_garmin_lifestyle_association` for an explicitly selected field's
presence versus recorded zero at a chosen lag. Missing entries are unknown.
Differences are unadjusted observations: discuss training, sleep, illness and
nutrition confounding, repeated testing and autocorrelation. Do not infer
medication causation or suggest changes. Omit analysis when daily aggregation or
timezone semantics are ambiguous.

Present observed trajectory, evidence, gaps and conditional training considerations.
Progression suggestions remain coaching judgment. Before describing a model as
predictive, evaluate chronological held-out sessions against a simple personal
baseline, reporting error, interval coverage and failure cases. Retrospective
daily summaries are not historical as-of forecasts. This skill does not authorize
workout/food changes, recurring tasks or medication changes.
