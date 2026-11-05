"""Deterministic logging questions, never inferred corrections or medical diagnoses."""
import hashlib
from collections import defaultdict
from datetime import date
from statistics import median

from .review_models import Finding, LogReview

RULE_VERSION = "1"


def analyze_logs(evidence):
    data = LogReview.model_validate(evidence)
    findings = []

    def add(source, rule, target, observed, question, confidence="medium"):
        key = f"{data.calendar_date}|{source}|{rule}|{target}"
        finding = Finding(finding_id=hashlib.sha256(key.encode()).hexdigest()[:24],
                          calendar_date=data.calendar_date, source=source, rule=rule,
                          target_id=target, evidence=observed, question=question, confidence=confidence)
        findings.append(finding.model_dump())

    diary = data.diary
    if diary is not None:
        if diary.complete is not True:
            add("nutrition", "diary_completeness", "day", "Diary completeness is unconfirmed.",
                "Is this the complete day's food diary, or is anything still unlogged?")
        if diary.calories_kcal is not None and diary.goal_kcal and diary.calories_kcal < diary.goal_kcal * data.calorie_goal_ratio:
            add("nutrition", "low_logged_calories", "day",
                f"Logged {diary.calories_kcal:g} kcal against a {diary.goal_kcal:g} kcal diary goal; this is not measured energy balance.",
                "Is the logged intake correct, or are meals, snacks, drinks or servings missing?")
        for meal in sorted(set(diary.missing_expected_meals)):
            meal_id = hashlib.sha256(meal.strip().casefold().encode()).hexdigest()[:24]
            add("nutrition", "expected_meal_missing", meal_id, f"Confirmed expected meal not found: {meal}"[:500],
                "Was this meal skipped, moved, or not logged?")
        for entry in sorted(set(diary.possible_duplicate_entry_ids)):
            add("nutrition", "possible_duplicate", entry, "Source review identified a possible duplicate food entry.",
                "Does this entry represent a separate serving, or is it a duplicate?", "low")
    for routine in data.routines:
        if not routine.confirmed or not routine.expected or date.fromisoformat(data.calendar_date).weekday() not in routine.weekdays:
            continue
        if routine.recorded in {"missing", "unknown"}:
            add("lifestyle", "routine_unconfirmed", routine.routine_id,
                f"No confirmed entry for the user-confirmed routine: {routine.label}"[:500],
                "Did you do this, skip it, forget to log it, or change the routine?")
        elif routine.recorded == "present" and routine.expected_amount is not None and routine.amount is not None and routine.amount != routine.expected_amount:
            add("lifestyle", "routine_amount_changed", routine.routine_id,
                f"Recorded {routine.amount:g} {routine.unit}; confirmed usual amount {routine.expected_amount:g} {routine.unit}.",
                "Is this quantity intentional, a logging error, or a change to the routine?")
    groups = defaultdict(list)
    for row in data.sets:
        target = hashlib.sha256(f"{row.activity_id}|{row.set_id}".encode()).hexdigest()[:24]
        if row.exercise_id is None or row.exercise_id.upper() == "UNKNOWN":
            add("strength", "unknown_exercise", target,
                f"Activity {row.activity_id}, set {row.set_id}: exercise not identified.",
                "Which exercise and equipment did you use for this set?")
        if row.load is not None and row.load_unit in {"unknown", "garmin_raw_unverified"}:
            # One question per activity, not one repeated question per set.
            if not any(f["rule"] == "unverified_load_units" and f["target_id"] == row.activity_id for f in findings):
                add("strength", "unverified_load_units", row.activity_id,
                    "Recorded load units or conventions are unverified; numerical load comparisons were omitted.",
                    "What units and load convention were used (total, per dumbbell, or assistance)?")
            continue
        if (row.exercise_id and row.equipment and row.comparison_group and row.kind == "work"
                and row.reps is not None and row.load is not None and not row.intentional_variation):
            groups[(row.activity_id, row.exercise_id, row.equipment, row.comparison_group, row.reps, row.load_unit)].append(row)
    for rows in groups.values():
        if len(rows) < 3:
            continue
        center = median(row.load for row in rows)
        if center <= 0:
            continue
        for row in rows:
            if abs(row.load - center) / center > data.weight_outlier_ratio:
                target = hashlib.sha256(f"{row.activity_id}|{row.set_id}".encode()).hexdigest()[:24]
                add("strength", "isolated_load_deviation", target,
                    f"Activity {row.activity_id}, set {row.set_id}: {row.load:g} {row.load_unit}; comparable work-set median {center:g} {row.load_unit}.",
                    "Was this load intentional, or should this set's recorded weight be corrected?", "low")
    for gap in data.gaps:
        add(gap.source, gap.kind, gap.record_id, gap.evidence,
            "Is this record correct, intentionally absent, awaiting sync, or in need of a correction?", "low")
    configured = [v for v in data.coverage if v.status != "not_configured"]
    usable = [v for v in configured if v.status in {"available", "partial"}]
    status = "failed" if not usable else "partial" if any(v.status != "available" for v in configured) else "completed"
    return {"status": status, "rule_version": RULE_VERSION, "calendar_date": data.calendar_date,
            "timezone": data.timezone, "as_of": data.as_of, "coverage": [v.model_dump() for v in data.coverage],
            "findings": findings, "finding_count": len(findings), "account_changes": False,
            "summary": ("No configured source supplied usable evidence." if status == "failed" else
                        f"{len(findings)} clarification findings; check coverage before interpreting absence of findings."),
            "limitations": ["Caller-provided evidence; source identity/date must be confirmed by the collecting agent.",
                            "Thresholds are configurable logging heuristics, not physiological or clinical limits.",
                            "Missing is unknown; no automatic food, supplement or exercise corrections.",
                            "Warmups, drop sets, intentional variation and unmatched/unverified loads are not compared."],
            "text_is_untrusted_data": True}
