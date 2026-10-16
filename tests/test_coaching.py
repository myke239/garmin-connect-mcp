"""Synthetic evidence only; no Garmin, MFP or medication account data."""
from copy import deepcopy
from datetime import date, timedelta
import asyncio

import pytest
from pydantic import ValidationError

from garmin_connect_mcp.coaching import (
    CoachingDay, analyze_day, collect_day, compare_outcomes, lifestyle_association,
)
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.server import create_server

DAY = "2026-10-16"
ZONE = "America/Los_Angeles"


def observation(day=DAY, value=50):
    return {"calendar_date": day, "timezone": ZONE, "fetched_at": "2026-10-16T10:00:00-07:00",
            "metrics": {"overnight_hrv_ms": {"value": value, "unit": "ms", "source": "garmin",
                                             "source_field": "hrvSummary.lastNightAvg"}}}


def history():
    return [observation((date.fromisoformat(DAY)-timedelta(days=index)).isoformat(), 30 if index == 0 else 50)
            for index in range(29)]


def analyze(**kwargs):
    return analyze_day(**{"calendar_date": DAY, "timezone": ZONE, "history": history(),
                          "nutrition": [], "check_in": {}, "sessions": [], **kwargs})


def test_baseline_excludes_today_and_reports_counts_without_prediction():
    result = analyze()
    metric = result["metrics"]["overnight_hrv_ms"]
    assert metric["baseline_observations"] == 28
    assert metric["median"] == 50 and metric["position"] == "below_recent_range"
    assert "sleep_duration_h" in result["missing_metrics"]
    assert "score" not in result
    assert len(result["provenance"]) == 29


def test_sparse_baseline_and_source_mismatch_do_not_make_normality_claims():
    rows = history()[:14]
    assert analyze(history=rows)["metrics"]["overnight_hrv_ms"]["baseline_status"] == "insufficient_data"
    rows = history()
    rows[0]["metrics"]["overnight_hrv_ms"]["source"] = "user"
    assert analyze(history=rows)["metrics"]["overnight_hrv_ms"]["baseline_observations"] == 0


@pytest.mark.parametrize("change", [
    {"timezone": "Europe/London"}, {"calendar_date": "2026-10-17"},
    {"fetched_at": "2026-10-16T10:00:00"},
])
def test_invalid_alignment_and_timestamps(change):
    row = {**observation(), **change}
    with pytest.raises((ValueError, ValidationError)):
        analyze(history=[row])


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, "50"])
def test_numeric_input_must_be_finite_and_typed(value):
    row = observation(value=value)
    with pytest.raises((ValueError, ValidationError)):
        CoachingDay.model_validate(row)


def test_units_and_unknown_fields_rejected():
    row = observation()
    row["metrics"]["overnight_hrv_ms"]["unit"] = "seconds"
    with pytest.raises(ValueError):
        CoachingDay.model_validate(row)
    with pytest.raises(ValueError):
        CoachingDay.model_validate({**observation(), "account_id": "private"})


def test_duplicate_dates_and_limits_rejected():
    with pytest.raises(ValueError):
        analyze(history=[observation(), observation()])
    with pytest.raises(ValueError):
        analyze(baseline_days=True)
    with pytest.raises(ValueError):
        analyze(nutrition=[{"date":DAY, "timezone":ZONE, "complete":False, "totals":{}}]*32)


def test_nutrition_preserves_missing_zero_and_never_adds_exercise_calories():
    result = analyze(nutrition=[{"date": DAY, "timezone": ZONE, "complete": False,
        "totals": {"calories": 1000, "protein": 0, "exercise": 500},
        "goals": {"calories": 2000, "protein": 100}}])
    food = result["nutrition"][0]
    assert food["logged"]["calories"] == 1000
    assert food["logged"]["protein"] == 0
    assert food["logged"]["carbohydrates"] is None
    assert food["goal_difference"]["calories"] == -1000
    assert food["complete"] is False
    assert "exercise" not in food["logged"]


def test_ordered_workouts_and_symptoms_require_review_not_clearance():
    sessions = [{"session_id": "run", "sport": "running", "duration_min": 30, "intensity": "easy"},
                {"session_id": "lift", "sport": "strength", "duration_min": 45, "intensity": "hard"}]
    result = analyze(check_in={"pain":True}, sessions=sessions)
    assert result["planned_sessions"][1]["prior_planned_minutes"] == 30
    assert result["planned_sessions"][1]["assessment"] == "requires_review"
    assert result["review_constraints"]


def outcomes(count=5):
    return [{"calendar_date": (date.fromisoformat(DAY)-timedelta(days=i+1)).isoformat(),
             "session_type": "matched-run", "metric": "pace_s_km", "value": 300+i*10,
             "completed": True} for i in range(count)]


def test_matched_outcome_reference_and_noncompletion_count():
    rows = outcomes(6)
    rows[-1]["completed"] = False
    result = compare_outcomes(DAY, "matched-run", "pace_s_km", rows)
    assert result["completed_sessions"] == 5 and result["matched_sessions"] == 6
    assert result["median"] == 320
    assert result["status"] == "historical_reference_only"
    assert compare_outcomes(DAY, "other", "pace_s_km", rows)["median"] is None
    rows[0]["calendar_date"] = DAY
    with pytest.raises(ValueError):
        compare_outcomes(DAY, "matched-run", "pace_s_km", rows)


def test_lagged_lifestyle_alignment_and_missing_zero_distinction():
    rows = history()
    events = [{"calendar_date": row["calendar_date"], "amount": 1 if i % 2 else 0}
              for i, row in enumerate(rows[1:])]
    events[-1]["amount"] = None
    result = lifestyle_association(DAY, rows, events, "overnight_hrv_ms", 1)
    assert result["status"] == "exploratory_unadjusted_association"
    assert result["excluded_days"] == 1
    assert result["recorded_zero_days"] + result["exposed_days"] == 27
    assert lifestyle_association(DAY, rows, events[:3], "overnight_hrv_ms")["difference_in_medians"] is None


class Service:
    def __init__(self):
        self.calls = []
        self.replies = {
            "get_sleep_data": {"dailySleepDTO": {"calendarDate":DAY, "sleepTimeSeconds":28800}},
            "get_hrv_data": {"hrvSummary": {"calendarDate":DAY, "lastNightAvg":0}},
            "get_stats": {"calendarDate":DAY, "restingHeartRate":60},
            "get_respiration_data": {"calendarDate":DAY, "avgSleepRespirationValue":15},
            "get_stress_data": {"calendarDate":DAY, "avgStressLevel":-1},
            "get_morning_training_readiness": {"calendarDate":DAY, "score":0, "inputContext":"AFTER_WAKEUP_RESET"},
        }

    def call(self, method, day):
        self.calls.append((method, day))
        raw = self.replies[method]
        if isinstance(raw, Exception):
            raise raw
        return deepcopy(raw)

    def meta(self):
        return {"cached":False, "fetched_at_utc":"2026-10-16T10:00:00-07:00"}


def test_collection_preserves_zero_but_excludes_sentinels_and_undated_values():
    service = Service()
    result = collect_day(service, DAY, ZONE)
    assert result["day"]["metrics"]["sleep_duration_h"]["value"] == 8
    assert result["day"]["metrics"]["garmin_readiness_score"]["value"] == 0
    assert "stress_score" not in result["day"]["metrics"]
    assert len(service.calls) == 6
    service.replies["get_stats"].pop("calendarDate")
    service.replies["get_morning_training_readiness"]["inputContext"] = "OTHER"
    result = collect_day(service, DAY, ZONE)
    assert "resting_hr_bpm" not in result["day"]["metrics"]
    assert "garmin_readiness_score" not in result["day"]["metrics"]


def test_collection_partial_errors_and_auth_stop():
    service = Service()
    service.replies["get_sleep_data"] = RequestError("NOT_FOUND")
    assert collect_day(service, DAY, ZONE)["availability"]["get_sleep_data"]["error_code"] == "NOT_FOUND"
    service.replies["get_sleep_data"] = RequestError("AUTH_REQUIRED")
    with pytest.raises(RequestError):
        collect_day(service, DAY, ZONE)


def test_new_tools_are_readonly_in_recovery_profile():
    tools = asyncio.run(create_server(tool_profile="recovery").list_tools())
    names = {tool.name:tool for tool in tools}
    assert names["get_garmin_coaching_day"].annotations.readOnlyHint
    assert names["analyze_garmin_daily_recovery"].annotations.readOnlyHint


def test_typed_mcp_inputs_reach_analysis_and_nested_contracts_are_discoverable():
    import json
    server = create_server(tool_profile="recovery")
    tools = {tool.name:tool for tool in asyncio.run(server.list_tools())}
    schema = tools["analyze_garmin_daily_recovery"].inputSchema
    assert "CoachingDay" in schema["$defs"]
    result = asyncio.run(server.call_tool("analyze_garmin_daily_recovery",{
        "calendar_date":DAY,"timezone":ZONE,"history":history(),
        "nutrition":[],"check_in":{},"sessions":[]}))
    assert json.loads(result[0].text)["metrics"]["overnight_hrv_ms"]["median"] == 50


def test_invalid_incomplete_outcomes_and_unmatched_exposures_are_not_ignored():
    rows = outcomes(1)
    rows[0].update(metric="session_rpe",value=20,completed=False)
    with pytest.raises(ValueError):
        compare_outcomes(DAY,"matched-run","session_rpe",rows)
    with pytest.raises(ValueError):
        lifestyle_association(DAY,[observation()], [{"calendar_date":"2026-10-01","amount":-1}],
                              "overnight_hrv_ms")
