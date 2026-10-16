# Coaching input contracts

`get_garmin_coaching_day(calendar_date, timezone)` returns `{day, availability}`.
Pass only `day` objects as `history` to `analyze_garmin_daily_recovery`.
History permits 91 unique dates in one timezone. Target day is excluded from the
14–90-day baseline window; 14 same-source, same-field prior observations are
required per metric. The p10/p90 ranges and minimum counts are descriptive
engineering choices, not clinical or Garmin thresholds.

Daily records contain calendar_date, timezone, offset-aware fetched_at and metrics.
Each metric has value, exact unit, source (`garmin` or `user`) and source_field.
Supported metrics/units:

| Key | Unit |
| --- | --- |
| sleep_duration_h | h |
| sleep_score | Garmin score |
| overnight_hrv_ms | ms |
| resting_hr_bpm | bpm |
| sleep_respiration_bpm | breaths/min |
| stress_score | Garmin score |
| body_battery_score | Garmin score |
| garmin_readiness_score | Garmin score |
| acute_load | Garmin load |
| skin_temperature_deviation_c | degC deviation |
| spo2_pct | % |

The collector populates only documented scalar mappings. Additional metrics
require independently sourced, dated, unit-labeled evidence. Do not derive
numbers from Garmin qualitative labels.

Nutrition projection: `{date,timezone,complete,totals,goals}`. Relevant MFP keys:
calories (kcal), carbohydrates/protein/fat (g). Other nutrients may be supplied but
are not analyzed yet. The caller must align identity/timezone; pasted records
cannot be authenticated by the analyzer. Meal labels are not timestamps. Water
intake does not establish hydration/electrolyte status. Never add imported exercise calories.

Check-in: optional `{fatigue:0..10,soreness:0..10,pain:boolean,illness_symptoms:boolean}`.
Sessions: `{session_id,sport,duration_min,intensity}`, in order; sports
running/cycling/swimming/strength/other; intensity easy/moderate/hard. Prior planned
minutes are exposure, not a physiological fatigue penalty.

Outcomes: `{calendar_date,session_type,metric,value,completed}`; at most one truly
matched session/date, prior 366 days. Metrics: pace_s_km, power_w, reps, session_rpe.
Five completed sessions enable descriptive ranges, not a calibrated model.
Keep noncompletion counts. Exercise/load/context matching is the caller's
responsibility; the tool cannot verify a free-text session_type.

Lifestyle: one selected field's `{calendar_date,amount}`, consistently measured
nonnegative quantities; zero explicitly recorded, null unknown. Do not convert
Garmin NO/missing quantity to zero. Aggregate detail amounts only if semantics
permit it. Lag 0–3 maps exposure day to outcome day. Seven matched days/group
permit display only, not statistical significance. Presence (>0) versus recorded
zero is not a dose-response analysis. Confounding, autocorrelation and multiple
testing remain unadjusted. Never use this result for medication advice.

Evidence references: [subjective athlete monitoring](https://pubmed.ncbi.nlm.nih.gov/26423706/),
[strength proximity-to-failure experiment](https://pubmed.ncbi.nlm.nih.gov/36752989/),
[nutrition and athletic performance](https://pubmed.ncbi.nlm.nih.gov/26891166/).
These support including context, not the clinical validity of these tools.

Strength exposure contract: `assess_garmin_strength_session(as_of,recent_sets,
planned_exercises,regional_check_in)`. as_of and performed_at require UTC offsets.
Recent sets need unique set_id, performed_at, exercise_id, equipment, regions,
reps and optionally external_load_kg, rir, warmup. Plans need exercise_id,
equipment, regions, planned_sets, planned_reps and optional external_load_kg.
Region names: quads, hamstrings, glutes, calves, chest, back, shoulders, biceps,
triceps, core, forearms. Regional check-ins have region, soreness (0–10) and pain.
Use explicit total external load in kg only when independently verified; preserve
unknown/bodyweight/assisted loads as null. The caller confirms muscle mapping;
the tool neither estimates recruitment fractions nor recovery hours.
