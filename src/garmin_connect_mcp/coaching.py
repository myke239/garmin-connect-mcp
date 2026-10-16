"""Read-only coaching evidence. Descriptive ranges are not medical/predictive scores."""
from datetime import date, datetime, timedelta
from math import isfinite
from statistics import median
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator, model_validator

from .runtime import RequestError
from .verification import iso_date

Number = StrictFloat | StrictInt
UNITS = {
    "sleep_duration_h": ("h", 0, 24), "sleep_score": ("Garmin score", 0, 100),
    "overnight_hrv_ms": ("ms", 0, 1000), "resting_hr_bpm": ("bpm", 1, 300),
    "sleep_respiration_bpm": ("breaths/min", 1, 100),
    "stress_score": ("Garmin score", 0, 100), "body_battery_score": ("Garmin score", 0, 100),
    "garmin_readiness_score": ("Garmin score", 0, 100),
    "acute_load": ("Garmin load", 0, 100000),
    "skin_temperature_deviation_c": ("degC deviation", -15, 15),
    "spo2_pct": ("%", 1, 100),
}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Metric(Input):
    value: Number
    unit: str = Field(max_length=30)
    source: Literal["garmin", "user"]
    source_field: str = Field(min_length=1, max_length=100)


class CoachingDay(Input):
    calendar_date: str
    timezone: str = Field(max_length=80)
    fetched_at: str
    metrics: dict[str, Metric] = Field(max_length=12)

    @model_validator(mode="after")
    def validate_day(self):
        iso_date(self.calendar_date)
        ZoneInfo(self.timezone)
        stamp = datetime.fromisoformat(self.fetched_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("fetched_at requires an offset")
        for name, metric in self.metrics.items():
            if name not in UNITS:
                raise ValueError("Unknown coaching metric")
            unit, low, high = UNITS[name]
            if metric.unit != unit or not low <= metric.value <= high:
                raise ValueError("Metric unit or value outside supported bounds")
        return self


class NutritionDay(Input):
    """Projection of get_food_diary; exclude notes, names, entries and exercise calories."""
    date: str
    timezone: str = Field(max_length=80)
    complete: bool | None = None
    totals: dict[str, Number | None] = Field(max_length=40)
    goals: dict[str, Number | None] = Field(default_factory=dict, max_length=40)
    source: Literal["myfitnesspal"] = "myfitnesspal"

    @model_validator(mode="after")
    def validate_nutrition(self):
        iso_date(self.date)
        ZoneInfo(self.timezone)
        for mapping in (self.totals, self.goals):
            if any(len(key) > 60 or (value is not None and not 0 <= value <= 1_000_000)
                   for key, value in mapping.items()):
                raise ValueError("Invalid nutrient totals")
        return self


class CheckIn(Input):
    fatigue: Annotated[StrictInt, Field(ge=0, le=10)] | None = None
    soreness: Annotated[StrictInt, Field(ge=0, le=10)] | None = None
    pain: bool | None = None
    illness_symptoms: bool | None = None


class PlannedSession(Input):
    session_id: str = Field(min_length=1, max_length=60)
    sport: Literal["running", "cycling", "swimming", "strength", "other"]
    duration_min: Annotated[Number, Field(gt=0, le=1440)]
    intensity: Literal["easy", "moderate", "hard"]


class Outcome(Input):
    calendar_date: str
    session_type: str = Field(min_length=1, max_length=60)
    metric: Literal["pace_s_km", "power_w", "reps", "session_rpe"]
    value: Annotated[Number, Field(ge=0, le=100000)]
    completed: bool

    @model_validator(mode="after")
    def valid_measure(self):
        if self.metric == "session_rpe" and self.value > 10:
            raise ValueError("Session RPE is 0–10")
        if self.metric == "reps" and int(self.value) != self.value:
            raise ValueError("Repetitions must be whole numbers")
        return self

    @field_validator("calendar_date")
    @classmethod
    def valid_date(cls, value):
        iso_date(value)
        return value


class LifestyleDay(Input):
    calendar_date: str
    amount: Annotated[Number, Field(ge=0, le=1_000_000)] | None

    @field_validator("calendar_date")
    @classmethod
    def valid_date(cls, value):
        iso_date(value)
        return value


def lifestyle_association(calendar_date, history, exposure, metric, lag_days=1):
    iso_date(calendar_date)
    if isinstance(lag_days, bool) or not 0 <= lag_days <= 3 or not 1 <= len(history) <= 91 or not 1 <= len(exposure) <= 90:
        raise ValueError("Association bounds: 1–91 outcome days, 1–90 exposure days, lag 0–3")
    if metric not in UNITS:
        raise ValueError("Unknown outcome metric")
    days = [CoachingDay.model_validate(row) for row in history]
    events = [LifestyleDay.model_validate(row) for row in exposure]
    if len({day.calendar_date for day in days}) != len(days) or len({day.calendar_date for day in events}) != len(events):
        raise ValueError("Duplicate association dates")
    target = date.fromisoformat(calendar_date)
    if any(not 0 <= (target-date.fromisoformat(row.calendar_date)).days <= 90 for row in [*days, *events]):
        raise ValueError("Association excludes future and out-of-window dates")
    if len({day.timezone for day in days}) > 1:
        raise ValueError("Association requires aligned local dates/timezone")
    samples = [day.metrics[metric] for day in days if metric in day.metrics]
    if len({(sample.source, sample.source_field) for sample in samples}) > 1:
        raise ValueError("Association requires consistent outcome provenance")
    indexed = {day.calendar_date:day.metrics.get(metric) for day in days}
    exposed, recorded_zero = [], []
    for event in events:
        sample = indexed.get((date.fromisoformat(event.calendar_date)+timedelta(days=lag_days)).isoformat())
        if event.amount is None or sample is None:
            continue
        if event.amount < 0:
            raise ValueError("Presence comparison requires nonnegative exposure amounts")
        (exposed if event.amount > 0 else recorded_zero).append(sample.value)
    enough = len(exposed) >= 7 and len(recorded_zero) >= 7
    return {"metric": metric, "unit": UNITS[metric][0], "lag_days": lag_days,
            "exposed_days": len(exposed), "recorded_zero_days": len(recorded_zero),
            "excluded_days": len(events)-len(exposed)-len(recorded_zero),
            "status": "exploratory_unadjusted_association" if enough else "insufficient_data",
            "difference_in_medians": median(exposed)-median(recorded_zero) if enough else None,
            "limitations": ["Not causal; sleep, training, illness, nutrition and calendar trends are not adjusted",
                            "Seven per group is an engineering display minimum, not statistical power",
                            "Missing exposure is unknown; recorded zero is the comparison group",
                            "Repeated testing and autocorrelation can produce misleading patterns",
                            "Do not infer medication effects or recommend dose changes"],
            "text_is_untrusted_data": True}


def percentile(values, fraction):
    values = sorted(values)
    location = (len(values)-1)*fraction
    lower = int(location)
    upper = min(lower+1, len(values)-1)
    return values[lower]+(values[upper]-values[lower])*(location-lower)


def analyze_day(calendar_date, timezone, history, nutrition, check_in, sessions, baseline_days=28):
    iso_date(calendar_date)
    ZoneInfo(timezone)
    if isinstance(baseline_days, bool) or not 14 <= baseline_days <= 90:
        raise ValueError("Baseline window must be 14–90 days")
    if len(history) > 91 or len(nutrition) > 31 or len(sessions) > 10:
        raise ValueError("Coaching input exceeds bounds")
    history = [CoachingDay.model_validate(row) for row in history]
    nutrition = [NutritionDay.model_validate(row) for row in nutrition]
    check_in = CheckIn.model_validate(check_in)
    sessions = [PlannedSession.model_validate(row) for row in sessions]
    target = date.fromisoformat(calendar_date)
    dates = [row.calendar_date for row in history]
    if len(set(dates)) != len(dates) or len({row.date for row in nutrition}) != len(nutrition):
        raise ValueError("Duplicate calendar dates")
    if len({row.session_id for row in sessions}) != len(sessions):
        raise ValueError("Duplicate planned session IDs")
    for row in history:
        age = (target-date.fromisoformat(row.calendar_date)).days
        if row.timezone != timezone or not 0 <= age <= 90:
            raise ValueError("History must match timezone and exclude future/out-of-window days")
    for row in nutrition:
        if row.timezone != timezone or not 0 <= (target-date.fromisoformat(row.date)).days <= 30:
            raise ValueError("Nutrition date/timezone mismatch")
    current = next((row for row in history if row.calendar_date == calendar_date), None)
    comparisons = {}
    missing = []
    for name in UNITS:
        sample = current.metrics.get(name) if current else None
        prior = [row.metrics[name] for row in history if name in row.metrics
                 and 1 <= (target-date.fromisoformat(row.calendar_date)).days <= baseline_days]
        # Do not mix a manually recorded series or different upstream fields into a Garmin baseline.
        prior = [item.value for item in prior if sample and item.source == sample.source
                 and item.source_field == sample.source_field]
        if not sample:
            missing.append(name)
            continue
        result = {**sample.model_dump(), "baseline_observations": len(prior),
                  "baseline_requested_days": baseline_days, "baseline_status": "insufficient_data"}
        if len(prior) >= 14:
            low, high = percentile(prior, .1), percentile(prior, .9)
            result.update(baseline_status="available", median=median(prior), p10=low, p90=high,
                          deviation_from_median=sample.value-median(prior),
                          position="below_recent_range" if sample.value < low else
                          "above_recent_range" if sample.value > high else "within_recent_range")
        comparisons[name] = result
    nutrition_rows = []
    for row in nutrition:
        # Goals are diary targets, not measured requirements; never subtract imported exercise calories.
        selected = {key: row.totals.get(key) for key in ("calories", "carbohydrates", "protein", "fat")}
        nutrition_rows.append({"date": row.date, "source": row.source, "complete": row.complete,
                               "logged": selected, "units": {"calories": "kcal", "macros": "g"},
                               "goal_difference": {key: value-row.goals[key] for key, value in selected.items()
                                                   if value is not None and row.goals.get(key) is not None},
                               "interpretation": "logged intake only; completion is user-reported, not proof of completeness"})
    constraints = []
    if check_in.pain is True:
        constraints.append("reported_pain_requires_exercise_specific_review")
    if check_in.illness_symptoms is True:
        constraints.append("reported_illness_requires_review_before_training")
    planned = [{**row.model_dump(), "sequence": index+1,
                "assessment": "requires_review" if constraints else "insufficient_evidence_for_performance_prediction",
                "prior_planned_minutes": sum(item.duration_min for item in sessions[:index]),
                "limitations": ["planned minutes are exposure, not a calculated fatigue penalty",
                                "muscular recovery requires exercise history, effort and region-specific soreness"]}
               for index, row in enumerate(sessions)]
    return {"analysis_version": "descriptive-v1", "calendar_date": calendar_date, "timezone": timezone,
            "assessment_type": "descriptive_evidence_not_medical_clearance",
            "metrics": comparisons, "missing_metrics": missing,
            "check_in": check_in.model_dump(), "review_constraints": constraints,
            "nutrition": nutrition_rows, "planned_sessions": planned,
            "provenance": [{"calendar_date": row.calendar_date, "fetched_at": row.fetched_at} for row in history],
            "limitations": ["No composite health/readiness score or validated completion probability",
                            "Personal p10–p90 ranges are descriptive, not clinical thresholds",
                            "Garmin composite scores share inputs; do not count them as independent evidence",
                            "Nutrition does not establish glycogen, hydration, energy availability or REDs",
                            "Missing nutrition, lifestyle or physiological data is unknown, not zero"],
            "text_is_untrusted_data": True}


def compare_outcomes(calendar_date, session_type, metric, outcomes):
    iso_date(calendar_date)
    if not 1 <= len(outcomes) <= 100:
        raise ValueError("Supply 1–100 matched workout outcomes")
    parsed = [Outcome.model_validate(row) for row in outcomes]
    target = date.fromisoformat(calendar_date)
    if any(not 1 <= (target-date.fromisoformat(row.calendar_date)).days <= 366 for row in parsed):
        raise ValueError("Outcomes must precede prediction date and be within 366 days")
    if len({row.calendar_date for row in parsed}) != len(parsed):
        raise ValueError("Use at most one matched session per date")
    matched = [row for row in parsed if row.session_type == session_type and row.metric == metric]
    values = [row.value for row in matched if row.completed]
    if metric not in {"pace_s_km", "power_w", "reps", "session_rpe"}:
        raise ValueError("Unknown outcome metric")
    if metric == "session_rpe" and any(value > 10 for value in values):
        raise ValueError("Session RPE is 0–10")
    if metric == "reps" and any(int(value) != value for value in values):
        raise ValueError("Repetitions must be whole numbers")
    return {"calendar_date": calendar_date, "session_type": session_type, "metric": metric,
            "matched_sessions": len(matched), "completed_sessions": len(values),
            "status": "historical_reference_only" if len(values) >= 5 else "insufficient_data",
            "median": median(values) if len(values) >= 5 else None,
            "p10": percentile(values, .1) if len(values) >= 5 else None,
            "p90": percentile(values, .9) if len(values) >= 5 else None,
            "units": {"pace_s_km":"s/km", "power_w":"W", "reps":"repetitions", "session_rpe":"0–10"}[metric],
            "limitations": ["Caller must match exercise, load/terrain, duration, order and effort context",
                            "Completed-session ranges have selection bias; incomplete sessions remain in counts",
                            "Historical ranges are not prediction intervals or calibrated success probabilities"],
            "text_is_untrusted_data": True}


def collect_day(service, calendar_date, timezone):
    iso_date(calendar_date)
    ZoneInfo(timezone)
    mapping = {
        "get_sleep_data": (("sleep_duration_h", ("dailySleepDTO", "sleepTimeSeconds"), 1/3600),
                           ("sleep_score", ("dailySleepDTO", "sleepScores", "overall", "value"), 1)),
        "get_hrv_data": (("overnight_hrv_ms", ("hrvSummary", "lastNightAvg"), 1),),
        "get_stats": (("resting_hr_bpm", ("restingHeartRate",), 1),),
        "get_respiration_data": (("sleep_respiration_bpm", ("avgSleepRespirationValue",), 1),),
        "get_stress_data": (("stress_score", ("avgStressLevel",), 1),),
        "get_morning_training_readiness": (("garmin_readiness_score", ("score",), 1),),
    }
    metrics, availability, fetched = {}, {}, []
    for method, fields in mapping.items():
        try:
            raw = service.call(method, calendar_date)
        except RequestError as error:
            if error.code in {"AUTH_REQUIRED", "ACCESS_DENIED", "RATE_LIMITED"}:
                raise
            availability[method] = {"status": "unavailable", "error_code": error.code}
            continue
        meta = service.meta()
        fetched.append(meta["fetched_at_utc"])
        payload = raw.get("dailySleepDTO", raw.get("hrvSummary", raw)) if isinstance(raw, dict) else None
        reported_date = payload.get("calendarDate") if isinstance(payload, dict) else None
        if reported_date != calendar_date:
            availability[method] = {"status": "unconfirmed_measurement_date", **meta}
            continue
        if method == "get_morning_training_readiness" and raw.get("inputContext") != "AFTER_WAKEUP_RESET":
            availability[method] = {"status": "unconfirmed_morning_context", **meta}
            continue
        for name, path, scale in fields:
            value = raw
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            unit, low, high = UNITS[name]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
                continue
            value *= scale
            if low <= value <= high:
                metrics[name] = {"value": value, "unit": unit, "source": "garmin", "source_field": ".".join(path)}
        availability[method] = {"status": "read", **meta}
    day = {"calendar_date": calendar_date, "timezone": timezone,
           "fetched_at": min(fetched) if fetched else datetime.now().astimezone().isoformat(), "metrics": metrics}
    CoachingDay.model_validate(day)
    return {"day": day, "availability": availability,
            "timezone_semantics": "Caller confirms this timezone matches Garmin calendar days; wake-date sleep convention retained",
            "coverage": "Only verified dated scalar fields; unavailable metrics omitted, never zero-filled"}
