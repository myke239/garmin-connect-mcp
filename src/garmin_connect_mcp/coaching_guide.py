"""Discoverable, executable coaching contracts with synthetic examples only."""
from .coaching import UNITS

NAMES = {
    "get_garmin_coaching_day", "analyze_garmin_daily_recovery", "assess_garmin_strength_session",
    "compare_garmin_workout_outcomes", "analyze_garmin_lifestyle_association",
}


def guide(schemas):
    day = {"calendar_date":"2026-01-02", "timezone":"America/Los_Angeles",
           "fetched_at":"2026-01-02T10:00:00-08:00", "metrics":{
               "overnight_hrv_ms":{"value":50,"unit":"ms","source":"user","source_field":"synthetic_demo"}}}
    return {
        "purpose":"Strength-first descriptive coaching evidence; no validated performance or medical model",
        "workflow":[
            "Confirm date/timezone/person and intended exercise sequence.",
            "Collect get_garmin_coaching_day.day; preserve availability and fetch times. Reuse history, request small batches.",
            "If available call MyFitnessPal get_food_diary(include_notes=false), same owner/date; project only date/complete/totals/goals and confirmed timezone.",
            "Call analyze_garmin_daily_recovery. For strength call assess_garmin_strength_session with independently confirmed set times/units/effort/regions.",
            "Use matched historical references and lifestyle associations only when inputs meet their specific requirements.",
            "Report observations, calculations, gaps and coaching judgment separately; do not modify accounts or automations.",
        ],
        "metric_units": {name:{"unit":spec[0],"input_bounds":[spec[1],spec[2]]} for name,spec in UNITS.items()},
        "limits": {
            "history_days":91,"baseline_window_days":[14,90],"baseline_min_observations":14,
            "nutrition_days":31,"planned_sessions":10,"recent_strength_sets":500,
            "planned_exercises":30,"regional_check_ins":11,"historical_outcomes":100,
            "outcome_min_completed":5,"lifestyle_exposure_days":90,"lifestyle_lag_days":[0,3],
            "lifestyle_min_per_group":7,
        },
        "input_schemas": {name:schemas[name] for name in sorted(NAMES) if name in schemas},
        "examples_are_synthetic":True,
        "examples":[
            {"tool":"analyze_garmin_daily_recovery", "arguments":{
                "calendar_date":"2026-01-02","timezone":"America/Los_Angeles","history":[day],
                "nutrition":[{"date":"2026-01-01","timezone":"America/Los_Angeles","complete":False,
                              "totals":{"calories":1800,"protein":100,"carbohydrates":None,"fat":60},
                              "goals":{"calories":2200}}],
                "check_in":{"pain":False},"sessions":[]},
             "expected":"Insufficient HRV baseline; carbohydrate unknown; calorie goal difference -400 is not measured energy deficit."},
            {"tool":"assess_garmin_strength_session", "arguments":{
                "as_of":"2026-01-02T12:00:00-08:00",
                "recent_sets":[{"set_id":"demo-1","performed_at":"2026-01-01T12:00:00-08:00",
                                "exercise_id":"bench","equipment":"barbell","regions":["chest","triceps"],
                                "reps":8,"external_load_kg":60,"rir":1}],
                "planned_exercises":[
                    {"exercise_id":"bench","equipment":"barbell","regions":["chest","triceps"],"planned_sets":3,"planned_reps":8,"external_load_kg":60},
                    {"exercise_id":"pressdown","equipment":"cable","regions":["triceps"],"planned_sets":2,"planned_reps":12}],
                "regional_check_in":[{"region":"triceps","soreness":3,"pain":False}]},
             "expected":"One overlapping work set in 24h; 480 kg-reps exact bench history; exercise 2 overlaps exercise 1. Not recovery clearance."},
            {"tool":"compare_garmin_workout_outcomes","arguments":{
                "calendar_date":"2026-01-10","session_type":"bench-60kg-barbell","metric":"reps",
                "outcomes":[{"calendar_date":f"2026-01-0{index+1}","session_type":"bench-60kg-barbell",
                             "metric":"reps","value":8+index,"completed":True} for index in range(5)]},
             "expected":"Median 10 reps, descriptive p10 8.4/p90 11.6; not a forecast."},
            {"tool":"analyze_garmin_lifestyle_association","arguments":{
                "calendar_date":"2026-01-02","history":[day],"metric":"overnight_hrv_ms","lag_days":1,
                "exposure":[{"calendar_date":"2026-01-01","amount":0},
                            {"calendar_date":"2026-01-02","amount":None}]},
             "expected":"One recorded-zero match, one excluded unknown; insufficient data, no effect claim."},
        ],
        "interpretation_rules":[
            "Percentile ranges and observation minima are descriptive engineering choices, not clinical thresholds.",
            "Garmin raw strength weights are unverified; never infer kg, per-set timestamps or RIR.",
            "Workout reference matching is caller-confirmed, including load, equipment, ROM, order and effort.",
            "Missing/partial food logs and diary-goal differences cannot establish underfueling or energy availability.",
            "Pain/illness requires review; favorable physiology does not establish exercise clearance.",
            "Composite Garmin scores share inputs; do not count them as independent votes.",
            "Lifestyle differences are unadjusted, not causal or medication advice.",
        ],
    }
