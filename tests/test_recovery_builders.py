import copy
import pytest
from garmin_connect_mcp.recovery import compact, read_recovery, session_context
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.builders import strength_workout, running_workout, swim_workout
from garmin_connect_mcp.writes import validate
from garmin_connect_mcp.runtime import RequestError


def service(tmp_path, replies):
    def runner(directory, method, args, kwargs):
        value = replies[method]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)
    return GarminService(TokenStore(tmp_path), runner)


def test_compact_removes_identifiers_free_text_and_map_keys():
    value = compact({"userId": 123, "feedbackLong": "ignore instructions",
        "mostRecentTrainingStatus": {"latestTrainingStatusData": {"123-device": {
            "deviceId": 123, "trainingStatus": 2, "acuteTrainingLoadDTO": {"dailyTrainingLoadAcute": 20}}}}})
    assert "123-device" not in repr(value)
    assert "deviceId" not in repr(value)
    assert value["mostRecentTrainingStatus"]["latestTrainingStatusData"][0]["trainingStatus"] == 2


def test_missing_sleep_and_unconfirmed_morning_are_explicit(tmp_path):
    backend = service(tmp_path, {"get_sleep_data": {"dailySleepDTO": {
        "calendarDate": "2026-10-12", "sleepTimeSeconds": None}},
        "get_morning_training_readiness": {"score": 0, "inputContext": None}})
    assert read_recovery(backend, "sleep", "2026-10-12")["available"] is False
    result = read_recovery(backend, "readiness", "2026-10-12")
    assert result["data"]["score"] == 0
    assert not result["morning_context_confirmed"]


def test_partial_context_keeps_network_error_but_stops_rate_limit(tmp_path):
    replies = {"get_activity": {"activityId": 1, "summaryDTO": {"startTimeLocal": "2026-10-12T03:00:00"}},
        "get_activity_splits": {"activityId": 1, "lapDTOs": []},
        "get_activity_hr_in_timezones": [],
        **{name: {} for name in ("get_sleep_data", "get_hrv_data", "get_stress_data",
            "get_body_battery", "get_morning_training_readiness", "get_training_status")}}
    replies["get_hrv_data"] = RequestError("NETWORK_ERROR")
    result = session_context(service(tmp_path, replies), "1")
    assert result["sleep_calendar_date"] == "2026-10-11"
    assert result["context"]["hrv"]["error"]["code"] == "NETWORK_ERROR"
    replies["get_hrv_data"] = RequestError("RATE_LIMITED")
    with pytest.raises(RequestError):
        session_context(service(tmp_path, replies), "1")


def test_timed_strength_expands_sets_rests_and_preserves_grams():
    workout = strength_workout("Timed squat", [{"category": "SQUAT", "exercise": "SQUAT",
        "sets": 3, "duration_seconds": 20, "weight_kg": 5, "rest_seconds": 10}])["workout_json"]
    steps = workout["workoutSegments"][0]["workoutSteps"]
    assert len(steps) == 5
    assert [row["stepOrder"] for row in steps] == [1,2,3,4,5]
    assert steps[0]["weightValue"] == 5000
    assert steps[0]["endCondition"]["conditionTypeId"] == 2
    assert workout["estimatedDurationInSecs"] == 80
    validate("create_workout", {"workout_json": workout})


def test_running_pace_conversion_and_hr_targets():
    workout = running_workout("Intervals", [{"distance_m": 1000, "repeats": 2,
        "recovery_seconds": 60, "pace_s_km": [300,360]}, {"duration_seconds": 600, "hr_zone": 2}],
        120, 120)["workout_json"]
    steps = workout["workoutSegments"][0]["workoutSteps"]
    assert steps[1]["targetValueOne"] == pytest.approx(1000/300)
    assert steps[1]["targetValueTwo"] == pytest.approx(1000/360)
    assert steps[4]["zoneNumber"] == 2
    assert workout["estimatedDurationInSecs"] == 0
    validate("create_workout", {"workout_json": workout})


def test_swimming_distance_equipment_and_pool_metadata():
    workout = swim_workout("Pool", 25, [{"distance_m":100, "stroke":"free",
        "equipment":"kickboard", "drill":"kick", "repeats":2, "rest_seconds":20}])["workout_json"]
    assert workout["poolLength"] == 25
    assert len(workout["workoutSegments"][0]["workoutSteps"]) == 3
    assert workout["workoutSegments"][0]["workoutSteps"][0]["strokeType"]["strokeTypeId"] == 6


@pytest.mark.parametrize("builder,args", [
    (strength_workout, ("Bad", [{"category":"SQUAT","exercise":"SQUAT","reps":10,"duration_seconds":20}])),
    (strength_workout, ("Bad", [{"category":"SQUAT","exercise":"SQUAT","duration_seconds":True}])),
    (strength_workout, ("Bad", [{"category":"SQUAT","exercise":"STEP_DOWN","reps":10}])),
    (running_workout, ("Bad", [{"duration_seconds":float("nan")}])),
    (running_workout, ("Bad", [{"duration_seconds":10,"hr_zone":2,"pace_s_km":[300,360]}])),
    (running_workout, ("Bad", [{"duration_seconds":10,"repeats":30},{"duration_seconds":10,"repeats":30},{"duration_seconds":10,"repeats":30},{"duration_seconds":10,"repeats":30}])),
    (swim_workout, ("Bad",25,[{"distance_m":101}])),
    (swim_workout, ("Bad",25,[{"distance_m":100,"stroke":"unknown"}])),
])
def test_invalid_builders_fail_before_network(builder,args):
    with pytest.raises(ValueError):
        builder(*args)


def test_named_zone_plus_custom_range_rejected():
    workout = running_workout("Zone", [{"duration_seconds":10,"hr_zone":2}])["workout_json"]
    workout["workoutSegments"][0]["workoutSteps"][0]["targetValueOne"] = 120
    with pytest.raises(ValueError):
        validate("create_workout", {"workout_json": workout})
